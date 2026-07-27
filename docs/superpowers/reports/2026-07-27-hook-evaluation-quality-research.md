# Deterministic Gate Quality Research (2026-07-27)

*Provenance note: this report began scoped to Claude Code hooks only
(original title: "Hook Evaluation Quality Research"). Per the
requester's own direction mid-session, it is reframed to cover
**deterministic gates** generally -- of which a Claude Code hook is one
realization among several. The filename is unchanged from its original
creation date/topic for git-history continuity; the content below is
current as of this reframe.*

## Scope

This repository has `evaluating-skill-quality` (a nine-dimension rubric
plus a deterministic shape checker for judging `SKILL.md` artifacts) but
no sibling skill for judging the quality of a **deterministic gate** --
a mechanism that enforces a policy decision without relying on model
choice. This report is research only: it inventories primary sources
(this repository's own gate artifacts and design history across every
realization it has, plus Anthropic's official Claude Code hooks
documentation and five other agent-tool vendors' own hook-equivalent
mechanisms, all fetched this session) and proposes an evaluation model a
future skill could apply. **It does not create that skill.** Building
it -- `SKILL.md`, a rubric, a shape checker -- is explicitly out of scope
here and deferred to a follow-up issue once an owner picks among the
options in [Next steps](#next-steps-decision-ready-options).

Labeled per `grounding-in-primary-sources`: `Fact:` claims are grounded
in a citation given alongside them (a file:line read this session, or a
URL fetched this session with the source's own text quoted);
`Speculation:` claims are this report's own synthesis and are marked as
such.

## Guiding principle (Decision, 2026-07-27)

Per the requester's own direction, stated as the model's central,
governing principle rather than one candidate dimension among many:

> A good deterministic gate is not defined by which specific mechanism
> realizes it. It must not assume a specific interface or workload; it
> loosely couples to whichever middleware or service is optimal for a
> given environment; its own implementation stays thin -- the minimum
> necessary to invoke that environment's mechanism and interpret its
> answer; and what it guarantees is **reproducibility of the decision**,
> not reuse of one literal artifact.

This is not invented from nothing. It converges, independently, with
three things this repository's own design history already states:

- Fact, `docs/superpowers/specs/2026-07-17-gate-audit-trail-tradeoff.md`
  (Addendum, "Write path -- one algorithm, per-context sink", read this
  session): "Not one universal path... **One feature, not two: entry
  schema, hash chain, append logic, and verify logic are identical
  everywhere; only the resolved sink directory and the anchoring step
  differ per context.**" This is the same principle, already applied to
  one sub-layer (the audit trail) of a gate, across the same four
  contexts named below.
- Fact, `docs/superpowers/specs/2026-07-18-cicd-gate-cluster-design.md`
  (read this session, lines 172-179): "an issue or PR is a retrospective
  if and only if the single registered retro-identity predicate --
  defined once ... and imported by every consumer -- says so; the
  auto-retro mechanism, all three gates below, and any CI backstop
  evaluate that one predicate and never re-derive it." And (lines
  66-70): "adapt the mechanism, not the literal string" -- an explicit
  mechanism-is-portable/literal-values-are-not split.
- Fact, the same design doc (lines 441-461): candidates are accepted or
  rejected in direct proportion to how "redistributable," "portable," or
  "environment-specific" they are -- commit signing is rejected outright
  because it "serves the sibling's remote-session signer program... too
  environment-specific to redistribute," while a registry-validation
  candidate is called "essential" precisely because "it is itself
  redistributable to every consumer repo."

**Speculation, flagged as such:** this repository's own design-only
future architecture (see
[Internal: gitapex's own design-only future architecture](#internal-gitapexs-own-design-only-future-architecture-all-four-domains-not-yet-built)
below) -- an embedded Rego policy engine evaluated identically regardless
of which of four contexts invoked it -- reads as the fullest possible
realization of this exact principle, though this report does not claim
the requester's own principle was drawn from that specific doc; the
convergence is offered as corroborating precedent, not as the principle's
origin.

## Scope: four realization domains

Rather than inventing new vocabulary, this report reuses this
repository's own already-named taxonomy verbatim. Fact, per
`docs/superpowers/specs/2026-07-17-zero-trust-threat-model.md:41-51`
(read this session):

> "Four distinct invocation contexts, each a different implicit trust
> level:
> 1. A git hook subprocess (pre-commit/pre-push), local machine or CI.
> 2. A Claude-Code-style PreToolUse/PostToolUse/Stop/SessionStart/
>    UserPromptSubmit hook subprocess.
> 3. A CI job step (ephemeral runner).
> 4. An MCP server subprocess (stdio only, #126) -- the least-trusted-by-
>    default context: the caller is an arbitrary MCP client, not the
>    agent harness itself..."

This report maps the requester's own scope directly onto these four,
already-established domains:

- **Domain 2** ("hooks"): the original scope of this report, covering
  Claude Code hooks and five other agent-tool vendors' equivalents
  (Codex, Gemini CLI, Devin, OpenClaw, HermesAgent) -- see
  [Internal: gitapex's own hook artifacts](#internal-gitapexs-own-hook-artifacts-and-design-history-domain-2-case-study)
  and the External subsections below.
- **Domain 3** ("CI/CD"): this repository's own `.github/scripts/`
  gate cluster -- see
  [Internal: gitapex's own CI/CD gate cluster](#internal-gitapexs-own-cicd-gate-cluster-domain-3-case-study)
  below.
- **Domain 4** ("MCP configuration"): thin in this repository's own
  shipped artifacts -- see
  [Internal: MCP-level gating](#internal-mcp-level-gating-domain-4)
  below, which states this gap explicitly rather than papering over it.
- **Domain 1** ("git hooks" -- pre-commit/pre-push): out of scope for
  this pass; this repository's own `pyproject.toml` lists `prek` (a
  pre-commit-hook runner) as a dev dependency, but no pre-commit/pre-push
  hook configuration was researched this session -- named here as an
  explicit gap, not silently omitted.

**Middleware is not a fifth domain.** `bash`, `jq`, `python3`, `git`, and
any cloud service a gate delegates to are a cross-cutting dependency
layer any of the four domains above may lean on -- see
[Dependent middleware](#dependent-middleware) below, which already
documents this for Domain 2 and is extended to Domain 3 in the CI/CD
inventory.

## Evaluation model structure

Mirrors `evaluating-skill-quality`'s own proven structure (a two-lane
split plus cross-cutting axes), extended with one new axis this report
proposes as central to the guiding principle above:

- **Two-lane split**: deterministic-shape checks (a script could grade
  these) vs. probabilistic-maturity dimensions (need judgment) -- see
  [Candidate quality dimensions](#candidate-quality-dimensions-research-proposal-not-a-shipped-rubric).
- **Axis: Compatibility awareness** -- already built for Domain 2 (the
  agent-tool matrix and dependent-middleware findings below); not yet
  extended to Domains 3-4 in this pass.
- **Axis: Reproducibility / Domain-coverage** (new, central to the
  guiding principle) -- for a given policy, how many of the four domains
  realize it, with what trust/coverage properties, and is that
  intentional defense-in-depth or an unnoticed gap? See
  [Reproducibility / Domain-coverage axis](#reproducibility--domain-coverage-axis)
  below.
- **Axis: Blast-radius / trust classification** -- carried over from the
  Domain-2-only draft (dimension 9 below), not yet generalized to all
  four domains explicitly.
- **Mechanism-fit test**: "which domain(s) should own this policy?" --
  reuses six criteria this repository's own CI/CD design doc already
  argues from, rather than inventing new ones; see
  [Mechanism-fit: which domain should own a policy?](#mechanism-fit-which-domain-should-own-a-policy)
  below.

## Primary sources consulted

### Internal: gitapex's own hook artifacts and design history (Domain 2 case study)

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
   plugin (caught by a Codex review on PR #433). **This policy's own
   third realization -- the CI/CD gate `gate_acm_issue_disclosure.py` --
   is the central worked example of the new Reproducibility axis below.**
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
13. **Middleware/toolchain dependencies, observed directly across all
    four shipped hook scripts** -- Fact: every one of
    `hooks/check-bash-safety.sh`, `hooks/check-issue-acm-disclosure.sh`,
    `hooks/check-template-overwrite.sh`, and
    `skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh`
    declares `#!/bin/bash` and uses `set -euo pipefail`, and every one
    invokes `jq` to parse stdin JSON and construct output JSON. Only two
    of the four (`check-bash-safety.sh`,
    `check_task_bash_safety.sh`) additionally use bash-specific `[[ ]]`
    conditionals; the other two (`check-issue-acm-disclosure.sh`,
    `check-template-overwrite.sh`) stay within POSIX-compatible `[ ]`
    tests and `case` statements, so `#!/bin/bash` there is a looser
    dependency than the `[[ ]]`-using pair's. Two of the four
    (`check-bash-safety.sh`, `check-issue-acm-disclosure.sh`)
    additionally shell out to `python3` (`scan_provenance.py`,
    `check_acm_present_or_waiver.py` respectively); one
    (`check-bash-safety.sh`) additionally invokes `git` directly
    (`rev-parse`, `merge-base`, `log`) for its push-time provenance scan.
    None of `bash`, `jq`, `python3`, or `git` are guaranteed present by
    Claude Code itself -- they are environment dependencies the hook
    author must ensure exist.

### Internal: gitapex's own CI/CD gate cluster (Domain 3 case study)

Researched this session, at the requester's own direction, to ground
Domain 3 with the same rigor as Domain 2 above.

14. **`docs/superpowers/specs/2026-07-18-cicd-gate-cluster-design.md`**
    (504 lines) -- Fact: a design doc analyzing "the sibling" repository
    (identified below, item 17) and proposing which of its already-built
    CI/CD gates to port into gitapex. **Confirmed unimplemented as
    described**: this repository has no `.gitapex/` directory, and none
    of the scripts the doc names as core/protection gates
    (`scripts/auto_retro.py`, `hooks/gate_merge_safety.py`,
    `hooks/gate_gh_cli.py`, `scripts/scan_ssot_schema.py`,
    `scripts/scan_ssot_drift.py`) exist anywhere in the checked-out repo
    (confirmed by direct `find`/`grep` this session). The doc's own
    governing principle -- separate mechanism (portable) from literal
    policy value (not portable), quoted in the Guiding principle section
    above -- and its explicit adoption filter ("redistributable" /
    "environment-specific") are the clearest existing articulation, in
    this repository's own words, of the guiding principle this report
    now adopts. Two internal inconsistencies the doc itself does not
    resolve, worth carrying forward rather than silently smoothing over:
    a checklist claims "seven" retro-family gates import one shared
    identity predicate, but nine of the doc's own gate blocks list that
    import (lines 490-491 vs. the registry data itself); and "candidate
    8," a "registry-hygiene lint" the doc's own Case-C rationale depends
    on to verify a declared backstop actually exists, is referenced but
    never defined anywhere in the 504 lines.
15. **What actually shipped instead, in `.github/scripts/`** -- Fact:
    11 real scripts exist (`gate_acm_issue_disclosure.py`,
    `gate_skill_audit_disclosure.py`, `gate_skill_rename_lifecycle.py`,
    `scan_retrospective_gate_drift.py`, `scan_toolchain_pin_drift.py`,
    `scan_apm_manifest_drift.py`, `gate_owasp_asi_mapping.py`,
    `gate_owasp_llm_mapping.py`, `sync_pr_publish.py`,
    `post_merge_retro.py`, `skill_description_diff.py`), none matching
    item 14's proposed names. `post_merge_retro.py`'s own docstring
    states plainly what happened to the big proposal: "Issue #314
    (sub-issue of #140): the minimal, GITHUB_TOKEN-only slice of #140's
    post-merge-auto-retro gate cluster." The full 15-gate registry
    architecture was scoped down to a much smaller, incrementally-shipped
    reality.
16. **`scan_retrospective_gate_drift.py` -- a textbook bottom-up gate
    origin, in this repository's own words.** Fact, its own docstring:
    "Issue #297 (refs #187, #242, #246): `merge-retrospective`'s Step 0
    requires, every cycle, a manual search of every `retrospective`-
    labelled issue for a commit on `main` citing it. Issue #187 proposed
    automating this as a meta-gate; #242 and #246 each ran that search by
    hand again and confirmed the meta-gate itself was never built." A
    proposal sat unbuilt through two separate incidents of repeated
    manual pain before the gate was actually written -- the precise
    incident-driven, bottom-up pattern the requester asked to have
    verified for the sibling repository, found instead already
    documented inside gitapex's own history.
17. **Explicit ports from `tvna/claude-md`** -- Fact, per
    `gate_owasp_asi_mapping.py`'s own docstring (line 4): "Issue #144
    ports `tvna/claude-md`'s OWASP Agentic Top 10 mapping" -- naming the
    sibling repository directly, by name, independent of the design
    doc's own repeated "the sibling" references (item 14).
    `gate_owasp_llm_mapping.py`'s own docstring (lines 6-11) names issue
    #145 and calls itself "a **sibling** gate to
    `gate_owasp_asi_mapping.py`, not an extension of it... Same
    discipline as the ASI gate" -- it does not name `tvna/claude-md`
    directly itself; that attribution for the LLM gate holds only by
    chaining through its stated sibling relationship to the ASI gate,
    not as an independent naming. **This session could not independently verify
    `tvna/claude-md`'s own repository content directly**: `add_repo` was
    called three times at the requester's own request and each attempt
    returned "MCP tool call requires approval" without resolving --
    everything in items 14-17 about the sibling's own gates is therefore
    *attributed to gitapex's own citations of it*, not independently
    confirmed against `tvna/claude-md` itself. Named as an open
    verification gap in
    [Open questions](#open-questions--blind-spots) below, not silently
    upgraded to independently-confirmed fact.
18. **The ACM-disclosure policy's third realization --
    `gate_acm_issue_disclosure.py`.** Fact, its own docstring (lines
    5-13): "#357's own investigation found that no workflow in this
    repository triggers on `issues:` events, so a missing ACM on an issue
    body... had no universal, environment-independent backstop -- only a
    per-session skill-trigger (probabilistic) and a PreToolUse hook
    (#413, which only fires where this repo's own hook harness is
    loaded). This script is that backstop's check-and-act half." This is
    the single clearest, already-real example in this repository of the
    guiding principle above: one policy (does an issue body carry an
    ACM), three independent realizations with three different trust
    properties (skill-trigger: probabilistic; hook: Domain-2-scoped;
    CI/CD gate: Domain-3, environment-independent), each compensating for
    what the others cannot guarantee. Developed further as the worked
    example for the new
    [Reproducibility / Domain-coverage axis](#reproducibility--domain-coverage-axis)
    below.
19. **Middleware/dependency consistency across the 8 gates most closely
    inventoried this session** (`gate_acm_issue_disclosure.py`,
    `gate_skill_audit_disclosure.py`, `gate_skill_rename_lifecycle.py`,
    `scan_retrospective_gate_drift.py`, `scan_toolchain_pin_drift.py`,
    `scan_apm_manifest_drift.py`, `gate_owasp_asi_mapping.py`,
    `gate_owasp_llm_mapping.py`) -- Fact: the "thin, stdlib-only, no
    network calls" pattern `hooks/check_acm_present_or_waiver.py` claims
    for itself does **not** hold uniformly on the CI/CD side. 5 of 8 are
    stdlib-only with zero network calls; 2 of 8
    (`gate_acm_issue_disclosure.py`, `scan_retrospective_gate_drift.py`)
    make live calls to `api.github.com` and require `GITHUB_TOKEN` --
    an inherent property of being check-*and*-act gates, not pure
    checks; and 1 of 8 (`scan_apm_manifest_drift.py`) imports PyYAML, a
    third-party dependency, breaking the stdlib-only claim outright
    despite its own docstring saying it can "run standalone." Separately,
    none of the 8 scripts (nor the workflows invoking four of them
    directly) pin a Python interpreter version, while `pyproject.toml`
    declares `requires-python = ">=3.12"` -- honored only when the same
    scripts run through their pytest counterparts under `uv run --frozen
    pytest`, meaning the same script executes under two different,
    unpinned-vs-pinned Python provenances depending on entry point.
20. **CI-gate-to-CI-gate duplication, and issue-citation convention
    consistency.** Fact: `gate_owasp_asi_mapping.py` and
    `gate_owasp_llm_mapping.py` are near-identical structurally and
    textually (`_validate_table_header`, `_parse_rows`,
    `VALID_STATUSES`), explicitly framed by the LLM gate's own docstring
    as deliberate ("a **sibling** gate... not an extension of it"). Of
    the 8 gates inventoried, 7 name a specific backing issue/PR/finding
    in their own header, matching the same issue-citing convention
    already observed on the hook side (items 1, 3, 6, 8 above);
    `scan_apm_manifest_drift.py` is the one outlier, framed purely as
    protecting a "single-source-of-truth invariant" with no issue number
    -- the same "standing invariant, no issue cited" pattern already seen
    on the hook side (`hooks/check-template-overwrite.sh`, item 4 above),
    so this pattern is not unique to either domain.

### Internal: gitapex's own design-only future architecture (all four domains, not yet built)

**Everything in this subsection is confirmed design-only, not shipped**:
this repository has no `.gitapex/` directory, `pyproject.toml` declares
no Rust/Go/`regorus` dependency, and a repository-wide search for
`regorus`/`.rego` outside `docs/` finds nothing (all confirmed by direct
inspection this session). Read carefully to avoid the mistake of citing
this material as describing gitapex's current behavior.

21. **`docs/superpowers/specs/2026-07-17-zero-trust-threat-model.md`**
    (198 lines) -- Fact, its own "Design-only scope" section (lines
    11-18): "No sandboxing, verification, or input-validation code is
    written by this pass." It describes a future gitapex as "a single
    static binary CLI (Rust provisional/Go later)... REDISTRIBUTED:
    independent organizations run their own copy against their own
    repos, with their own adopter-authored `.rego` policy files" -- an
    embedded Rego (Open Policy Agent-family) policy-evaluation engine,
    entirely unbuilt today. It is also the source of the four-domain
    taxonomy this report adopts (see
    [Scope: four realization domains](#scope-four-realization-domains)
    above) and all seven zero-trust principles quoted where relevant
    throughout this report (lines 78-92: no implicit trust from
    location/ancestry; every invocation re-validates its own inputs;
    least privilege everywhere; assume breach; verified identity over
    asserted identity; fail closed including on INDETERMINATE; minimize
    information disclosure -- "applied as one... not selectively invoked
    to justify a decision already made on other grounds," lines 94-97).
    Its own "Consolidated findings" section records, for the
    MCP-server-mode design specifically (#126): "MCP mode inherits the
    CLI's full ambient privileges (env vars, credentials) though the
    advisory tools need only repo-tree read and local Rego evaluation" --
    one of several places this design-only material speaks directly to
    Domain 4, alongside the four-invocation-contexts list itself (which
    names the MCP server subprocess as "the least-trusted-by-default
    context," already quoted above) and its own `#126`
    Consolidated-findings subsection's other bullets (stdio parentage
    not being an implicit trust boundary, an `explain_denial`
    gate-evasion-oracle risk over MCP, and a trust-on-first-use
    bootstrapping gap in its tool-poisoning allowlist).
22. **`docs/superpowers/specs/2026-07-17-gate-audit-trail-tradeoff.md`**
    (344 lines) -- Fact: designs an audit-trail schema (hash-chained
    JSONL, a `policy_version` content hash, a `verified`/`asserted`
    identity split) that a gate must produce to prove it actually ran
    and what it decided -- not merely that it is configured to exist.
    Its own F5 finding makes this a precondition, not an aspiration:
    "audit-write failure MUST deny the gated operation... This creates a
    real, deliberate availability-vs-security tradeoff... record it as
    an accepted, explicit tradeoff." Eight distinct tradeoffs are named
    explicitly in the doc (hash-chaining vs. Merkle+Ed25519;
    mandatory-vs-optional extension tiers; zero-server JSONL vs. a REST
    collector; commit-to-git vs. `.gitignore`; availability vs. security
    on audit-write failure; signature non-repudiation vs. content
    truthfulness; file-mode 0600 vs. hash-chain integrity; and
    `policy_version` self-reporting's own blind spot against a
    compromised evaluator). Its "one algorithm, per-context sink"
    passage, already quoted in full in the Guiding principle section
    above, is this repository's own clearest existing precedent for the
    requester's proposed principle.

### Internal: MCP-level gating (Domain 4)

**Genuinely thin, named as a real gap rather than papered over.** This
repository has no `.mcp.json` or other committed MCP server
configuration (confirmed by a repository-wide search this session), so
Domain 4 has no shipped gitapex artifact to inventory the way Domains 2
and 3 do. What exists instead:

- Fact: `hooks/check-issue-acm-disclosure.sh`'s matcher is
  `mcp__github__issue_write` (item 3 above) -- this is a **Domain-2**
  artifact (a Claude Code hook) that happens to intercept an MCP tool
  call; it is not a Domain-4 artifact (an MCP server itself enforcing
  something), and this report does not conflate the two.
- Fact, per <https://code.claude.com/docs/en/hooks-guide> (fetched
  2026-07-27; two separate passages from the page, quoted separately
  rather than stitched into one, since they are not adjacent). The
  "Hooks and permission modes" section: a hook returning `"allow"`
  "doesn't bypass deny rules from settings, and it can't suppress the
  prompt for connector tools... or MCP tools marked
  `requiresUserInteraction`." A separate, earlier paragraph near the
  `"allow"`/`"deny"`/`"ask"` decision-value list makes the same point in
  different words: "...and so are connector tools [your organization
  set to `ask`] and MCP tools marked [`requiresUserInteraction`]. This
  means deny rules from any settings scope, including [managed
  settings], always take precedence over hook approvals." Together, both
  passages establish that this is Domain-4-adjacent gating this
  repository does not own or control -- it is imposed by whichever
  organization's own connector/managed settings apply to a given
  session, external to any file in this repository.
- Fact, per item 21 above: the design-only zero-trust doc calls the MCP
  server subprocess context "the least-trusted-by-default context" and
  records that its own #126 design currently "inherits the CLI's full
  ambient privileges" rather than a scoped subset -- a named,
  unaddressed risk in the design-only material, not a shipped
  mitigation.

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
  documented guarantee, not an assumption. (See also
  [Internal: MCP-level gating](#internal-mcp-level-gating-domain-4)
  above for a separate, related passage's connector/MCP-tool
  implications -- drawn from a different paragraph of the same page,
  not this same one.)
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

### External: other agent-tool hook mechanisms (fetched this session)

Researched at the requester's own direction, mirroring the scope
`evaluating-skill-quality`'s own `references/runtime-compatibility.md`
already tracks for skills: Claude Code, Codex, Gemini CLI, Devin,
OpenClaw, and HermesAgent. Each finding below uses that same document's
three evidence states (Documented / Unknown / Conflict), and every
runtime was checked against its own official docs or source repository,
not a memory or a third-party summary, per this session's own
`grounding-in-primary-sources` discipline.

- Fact, per `github.com/openai/codex` (`docs/config.md`,
  `codex-rs/hooks/src/**`, `codex-rs/core/src/hook_runtime.rs`, and the
  generated JSON schema `codex-rs/hooks/schema/generated/pre-tool-use.
  command.output.schema.json`, all fetched this session): **Documented.**
  Codex has an 11-value `HookEventName` enum (including `PreToolUse`,
  `PostToolUse`, `SessionStart`, `SessionEnd`), regex matchers on 9 of the
  11 events, a `PreToolUseHookResult::Blocked` variant, and a JSON output
  contract using the identical field name
  `hookSpecificOutput.permissionDecision: "allow"|"deny"` Claude Code
  uses. Codex's own source names its lineage directly:
  `codex-rs/features/src/lib.rs` reads "Enable Claude-style lifecycle
  hooks loaded from hooks.json files."
- Fact, per `google-gemini/gemini-cli`'s official docs
  (`docs/hooks/{index,reference,writing-hooks}.md`, fetched this
  session): **Documented.** "Hooks run synchronously as part of the
  agent loop -- when a hook event fires, Gemini CLI waits for all
  matching hooks to complete before continuing." Named events
  (`BeforeTool`/`AfterTool` etc.) map closely to Claude Code's
  Pre/PostToolUse; blocking uses `"decision": "deny"` (aliased
  `"block"`); exit codes carry the same 0/2/other semantics. The docs
  define a `CLAUDE_PROJECT_DIR` alias environment variable "provided for
  compatibility" -- an explicit, named interoperability gesture toward
  Claude Code specifically.
- **Unknown** for Devin (Cognition): this session's own outbound proxy
  policy blocked every fetch attempt against `docs.devin.ai` (a
  CONNECT-stage 403, not a site-side failure). Search-index page titles
  suggest hooks documentation exists there, but per this report's own
  sourcing discipline an indexed title and a search engine's own summary
  paraphrase are not a primary source -- this is recorded as an
  environment-caused verification gap, not as evidence the mechanism is
  absent, and not upgraded to Documented on an unverified paraphrase.
- Fact, per `openclaw/openclaw`'s official docs
  (`docs/automation/hooks.md`, `docs/plugins/hooks.md`, fetched this
  session): **Documented**, with a structural divergence worth flagging
  on its own. OpenClaw splits its mechanism into "internal hooks"
  (event-driven, explicitly side-effect-only, cannot block) and "typed
  plugin hooks" (registered via a Plugin SDK call, `before_tool_call` can
  return `{block: true, blockReason}`). Unlike Claude Code, Codex, Gemini
  CLI, and HermesAgent -- all of which transport a blocking decision via
  an external process reading JSON on stdin and signaling via exit
  code/stdout JSON -- OpenClaw's blocking path is an **in-process
  JS/TS function return value**, a different transport model entirely.
  The same source material also surfaced two historical bug reports
  (`openclaw/openclaw` issues #5943, #5513) that `before_tool_call` was
  "defined... but never called" in an earlier version, reportedly
  addressed later -- a documented design contract is not the same claim
  as verified current live behavior, and this report does not conflate
  the two.
- Fact, per `NousResearch/hermes-agent`'s official docs
  (`website/docs/user-guide/features/hooks.md`, fetched this session):
  **Documented**, with a second structural divergence. Hermes's Shell
  Hooks explicitly accept Claude Code's own JSON shape as an alternate
  input format -- the doc's own comment reads `// Claude-Code style` next
  to `{"decision": "block", "reason": "..."}` -- a direct, named
  cross-vendor compatibility gesture. But Hermes's blocking is driven
  **purely by the JSON payload's `action`/`decision` field**: a nonzero
  exit code, a malformed response, or a timeout is only logged as a
  warning and never blocks anything, the inverse of Claude Code's
  exit-code-2-is-authoritative convention. A hook script written to rely
  on Claude Code's exit-code contract would silently stop enforcing its
  policy if the same check needed to run under Hermes's own hook system.
- Fact, per a dedicated search this session (queries including
  "agentskills.io hooks specification" and "AI agent lifecycle hooks
  standard"): **no open cross-vendor hooks specification exists**,
  unlike Agent Skills' `agentskills.io`, which all six runtimes above
  separately claim compatibility with. A small number of early,
  unadopted proposals exist (AgentHook, a v0.2 draft self-described as
  "not yet endorsed by any external runtime"; the Agent Control Standard,
  a v0.1 public preview with no vendor implementations; the Standard
  Agent Specification) but none has a single confirmed vendor adopter.
  Practically: two of the five other tools researched this session
  (Codex, HermesAgent) explicitly name Claude Code's own hook shape in
  their own source or docs as something they converged toward or
  interoperate with, so Claude Code's contract already functions as a
  de facto reference shape industry-wide, without a governing spec
  enforcing that convergence stays exact.

### External: vendor rationale and design-philosophy statements (fetched this session)

A follow-up sweep, distinct from the structural comparison above: not
"does an equivalent mechanism exist" but "does this vendor's own prose
say *why* it exists, or state a hook-writing philosophy the way
Anthropic's own docs do (`grounded above`)." **Scope note, stated
explicitly rather than left to look like an unbroken continuation of
the same five-vendor set:** this sweep covers Codex, Gemini CLI,
OpenClaw, and HermesAgent (four of the original five, re-researched for
rationale specifically) plus **Cursor**, a sixth vendor added only for
this follow-up sweep, not part of the structural-comparison section's
five. Devin is not re-attempted here -- its primary-source domain was
already confirmed blocked in the structural comparison above, and this
sweep did not re-attempt it; see
[Open questions](#open-questions--blind-spots) below, which already
names Devin's own hook mechanism as unresolved. Same primary-source
discipline throughout: a claim not found in the fetched text is
reported as absent, never invented to fill the question.

- Fact: Codex's own accessible sources (`docs/config.md`, the entire
  `codex-rs/hooks` crate's doc comments) are **silent** on rationale --
  no "why hooks exist," no hook-vs-model-judgment framing, no
  best-practices prose anywhere found. The only hooks-related prose in
  `docs/config.md` is a two-sentence admin-config note about
  `allow_managed_hooks_only`. (`developers.openai.com/codex/hooks`, a
  separately hosted docs site that might carry more, was blocked by this
  session's own network policy and remains unverified.)
- Fact, per `google-gemini/gemini-cli`'s own docs: frames hooks around
  extensibility, not determinism-over-judgment -- "allowing you to
  intercept and customize behavior without modifying the CLI's source
  code," with named use cases "Validate actions: ...block potentially
  dangerous operations" and "Enforce policies: ...security scanners and
  compliance checks." Two concrete, vendor-original design points not
  found in Anthropic's own docs: (a) a strict I/O-hygiene rule --
  "**Silence is Mandatory**: Your script must not print any plain text
  to stdout other than the final JSON object. Even a single `echo` or
  `print` call before the JSON will break parsing"; (b) a runtime
  tamper-*detection* mechanism, weaker than tamper-*prevention* -- worth
  stating precisely rather than overclaiming its strength: project-level
  hooks are **fingerprinted**, and "if a hook's name or command changes
  (for example, via `git pull`), it is treated as a new, untrusted
  hook." Per `docs/hooks/best-practices.md`'s own "Project Hook
  Security" flow, this does **not** gate execution on re-approval -- the
  documented sequence is detect, warn, then **execute by default**
  ("unless specific security settings block it"). A named risk
  statement: "Hooks execute arbitrary code with your user privileges."
- Fact, per `openclaw/openclaw`'s own docs: no "why" framing either, but
  concrete, vendor-original hook-writing guidance -- "Keep handlers
  fast," "Handle errors gracefully. Wrap risky operations in try/catch;
  do not throw so other handlers can run," "Filter events early," "Keep
  the allowlists conservative." One principle independently converges
  with this repository's own zero-trust doctrine
  (`docs/superpowers/specs/2026-07-17-zero-trust-threat-model.md`'s own
  principle 6, "fail closed, including on INDETERMINATE," item 21
  below): "**Missing fields are unproven, not false
  assurances; fail closed when policy requires them.**" A named risk:
  "A timed-out handler promise continues running because hook callbacks
  do not receive a cancellation signal."
- Fact, per `NousResearch/hermes-agent`'s own docs: also no explicit
  determinism-vs-judgment framing, but one genuine design-philosophy
  statement, recounting a past mistake -- an earlier Hermes version
  "shipped this as a built-in hook and silently spawned an agent with
  bare defaults on every gateway boot. That surprised users... Keeping
  it as a documented pattern -- built by you, in your hooks directory --
  means you see exactly what it does and opt in by writing the files."
  A named risk, stated as a direct analogy: "Shell hooks run with your
  full user credentials -- same trust boundary as a cron entry or a
  shell alias." A concrete idempotency rule: "Make it idempotent: the
  hook re-fires after each nudge, so gate on `attempt`... otherwise it
  just nudges until the bound is hit."
- **Unverified** for Cursor: every fetch attempt against `cursor.com`
  and `docs.cursor.com` was blocked by this session's own outbound
  network policy (confirmed as a general egress restriction, not a
  Cursor-specific block, via a control fetch to an unrelated blocked
  domain and a successful fetch to an allowed one). Third-party blog
  summaries paraphrase Cursor's hooks as "deterministic" against
  AI-interpreted "suggestions," but that phrasing was never independently
  confirmed against Cursor's own primary text this session, so it is not
  reported as a vendor quote.
- Cross-cutting finding, not attributable to any single vendor: **none
  of the five other runtimes researched this session articulate an
  explicit hook-vs-model-judgment philosophy the way Anthropic's own
  docs do** ("deterministic control... rather than relying on the LLM to
  choose to run them," already grounded above) or the way this
  repository's own `evaluating-skill-quality` rubric independently does
  ("Skill vs. hook" mechanism-fit test). Their documented guidance is
  overwhelmingly mechanical or narrowly practical (I/O hygiene, error
  handling, idempotency) rather than doctrinal. This repository's own
  explicit mechanism-fit doctrine is closer to an outlier than an
  industry norm -- worth naming plainly rather than assuming the rest of
  the field already agrees on it.

## Compatibility awareness (agent-tool axis and dependent middleware)

**Scoped to Domain 2 only in this pass** -- not yet extended to Domains
3-4. A warning-only axis, proposed here to mirror `evaluating-skill-quality`'s
own explicitly separate "Compatibility awareness" axis (its
`references/runtime-compatibility.md`) rather than folding it into the
numbered dimensions above -- same structural choice, same scope of
runtimes tracked (Claude Code, Codex, Gemini CLI, Devin, OpenClaw,
HermesAgent), same three evidence states. Like its skill-side
counterpart, this axis never changes a hook's own pass/fail verdict on
its own; it is a disclosure requirement layered on top.

### Why this is not a "Portability" axis, named explicitly

`evaluating-skill-quality` keeps two axes deliberately separate:
**Portability level** (does *this skill's own text* run unmodified
wherever it is vendored -- a property of the artifact's own reusability)
and **Compatibility awareness** (do *this skill's own claims* about
external runtime behavior hold up against the tracked runtime matrix --
a factual-accuracy check, not a reusability goal). This section is a
hook-side analogue of the second axis only. It should not borrow
"Portable" as a label at all, for a reason worth stating plainly rather
than glossing over: a skill's portability *compounds* -- the same
unmodified text pays for itself again, at no extra authoring or
verification cost, every additional repository or harness it is vendored
into. Cross-tool coverage for a hook has no such compounding return. Per
the divergences the runtime matrix below documents (OpenClaw's blocking
decision is an in-process SDK return value, not an external process plus
exit code; HermesAgent's blocking authority is the JSON payload's own
field, with exit code carrying none), a hook enforcing the same policy
under a different tool is not "the same artifact reused" -- it is a
**separate, independently authored and independently verified
mechanism**, paid for again in full each time. Pursuing "compatibility"
here does not compound the way pursuing skill portability does; it is a
linear, per-tool cost, so this section deliberately does not score
"Portable" as a virtue and does not propose a Portability-level-style
declared axis for hooks at all.

This axis is, like its skill-side counterpart, **a lens applied to the
specific hook under review** -- grading whether *that hook's* own
documentation or comments correctly state which enforcement signal is
authoritative, which transport it assumes, and what happens to its own
policy if the repository were worked on through a different tool --
never a requirement that some future `evaluating-hook-quality` skill (or
this report itself) be usable across those other tools. That latter
question, if it ever matters, is `evaluating-skill-quality`'s own job
once such a skill exists and is reviewed by it (every skill in this
repository already declares its own Portability level and Compatibility
posture) -- it is not a property this axis needs to invent a second
time under a different name.

### Agent-tool runtime matrix

| Agent tool | Deterministic hook-equivalent exists? | Structural comparison to Claude Code hooks | Evidence state |
|---|---|---|---|
| Codex (OpenAI) | Yes | Own source calls it "Claude-style lifecycle hooks"; 11 named events; regex matchers on 9/11; `hookSpecificOutput.permissionDecision` field name identical to Claude Code's; exit 0 success / nonzero failure. | Documented |
| Gemini CLI | Yes | Named events map closely to Pre/PostToolUse; `decision: "deny"/"block"`; exit-code 0/2/other convention identical in shape; defines a `CLAUDE_PROJECT_DIR` alias "provided for compatibility." | Documented |
| Devin (Cognition) | Indexed doc titles suggest yes | Not independently verified this session -- the primary-source domain was blocked by this session's own outbound proxy policy, not by any evidence the mechanism is absent. | Unknown |
| OpenClaw | Yes, split into two layers | Blocking layer ("typed plugin hooks") transports its decision as an **in-process SDK function return value**, not an external process + JSON/exit-code, unlike every other runtime in this table; a documented historical bug shows the design contract and verified live behavior are not automatically the same claim. | Documented (design); live behavior unverified beyond docs |
| HermesAgent | Yes | Explicitly accepts Claude Code's own JSON shape as an alternate format ("`// Claude-Code style`"); blocking is JSON-payload-driven only -- exit code carries **no** blocking meaning, the inverse of Claude Code's own convention. | Documented |
| *(no open cross-vendor spec)* | -- | Unlike Agent Skills' `agentskills.io`, no governing standard exists; convergence toward Claude Code's shape (Codex, HermesAgent) is voluntary, not spec-enforced. | Documented (absence confirmed by search) |

### Candidate compatibility-awareness checks

- **Transport-model disclosure.** Does the hook's own documentation state
  whether its blocking mechanism is external-process-plus-exit-code
  (Claude Code, Codex, Gemini CLI, HermesAgent's Shell Hooks) or
  in-process-SDK-return-value (OpenClaw's typed plugin hooks)? A rubric
  built only against Claude Code's own contract would silently assume
  the wrong transport if the same policy needed porting.
- **Blocking-signal-of-record disclosure.** Does the hook state which
  signal is authoritative for blocking -- exit code (Claude Code) or the
  JSON payload's own field (HermesAgent, where exit code is
  non-authoritative)? Porting a hook that only sets exit code 2, with no
  JSON payload, to a Hermes-style runtime would silently stop enforcing
  it.
- **Documented-vs-verified distinction, carried into the hook's own
  claims.** Per OpenClaw's own historical `before_tool_call` bug: a
  runtime's documentation describing a blocking contract is not proof
  that contract is live in the currently-installed version. A rubric
  could ask whether a hook's own claims about *any* runtime's behavior
  (including Claude Code's) cite a verified, current observation
  (per this repository's own `threat-model-and-authorization.md`
  precedent, item 7 above) rather than the runtime's documentation
  alone.

### Dependent middleware

Grounded in the internal inventory above (item 13, extended to Domain 3
by item 19): every hook script this repository ships already depends on
external binaries Claude Code itself does not guarantee -- `bash`
specifically (not POSIX `sh`), `jq` universally, `python3` in two of
four scripts, and `git` in one. This is not hypothetical: Anthropic's
own hooks-guide troubleshooting section names both failure modes
directly as known issues, not edge cases -- "`jq`: command not found...
install `jq` or use Python/Node.js for JSON parsing," and, on Windows
specifically, that Git Bash "still source[s] your profile. If that
profile contains unconditional `echo` statements, the output gets
prepended to your hook's JSON" and breaks JSON parsing entirely. On the
CI/CD side, the same "thin, no third-party dependency" property holds
for 5 of 8 gates inventoried but is broken outright by
`scan_apm_manifest_drift.py`'s `import yaml` (item 19) -- middleware
dependency is a real, cross-domain concern, not one confined to Domain 2.

- **Candidate check: middleware dependency is stated, not assumed.**
  Does the gate's own comments or documentation name every external
  binary or third-party package it depends on, so a consumer repository
  (or a different deployment image, container, or CI runner) can verify
  each is present before relying on the gate, rather than discovering a
  silent failure the first time the dependency is missing?
- **Candidate check: shell-portability is a deliberate choice, not a
  default.** A `#!/bin/bash` shebang using `set -euo pipefail` and
  `[[ ]]`/array syntax is a deliberate choice to require bash over
  POSIX `sh` -- does the hook's own documentation say so, given bash is
  not universally preinstalled (minimal container images, some CI
  runners) the way `sh` typically is?
- **Candidate check: Windows-specific execution-model awareness.**
  Given the official docs' own -- confirmed this session -- statements
  that (a) Windows exec-form hooks cannot spawn `.cmd`/`.bat` shims
  (`npm`, `npx`, `eslint`, etc.) without going through `node` directly,
  and (b) Git Bash's profile-sourcing behavior can silently corrupt a
  hook's JSON output, does a hook likely to run on Windows disclose
  either constraint, rather than being authored and tested on
  macOS/Linux only and assumed portable?
- **Candidate check: interpreter/runtime version pinning.** Grounded in
  item 19's finding that the same CI/CD gate scripts run under two
  different, unpinned-vs-pinned Python provenances depending on entry
  point -- does a gate's own execution environment pin the interpreter
  version its author actually tested against, or silently inherit
  whatever the invoking context's own default happens to be?

## Reproducibility / Domain-coverage axis

**New axis, central to the guiding principle above.** For a given
policy, this axis asks: in how many of the four domains is it realized,
with what trust/coverage properties, and is the resulting overlap (or
gap) a deliberate, argued decision or an unnoticed accident?

### Worked example: the ACM-disclosure policy (item 18)

The clearest case already real in this repository. One policy -- "does
an issue body carry an Acceptance Criteria Map or an explicit waiver" --
realized three times:

| Realization | Domain | Trust/coverage property |
|---|---|---|
| `skills/drafting-an-acm-issue/SKILL.md` | (per-session, not domain-scoped) | Probabilistic -- depends on the agent choosing to invoke the skill |
| `hooks/check-issue-acm-disclosure.sh` | 2 (Claude Code hook) | Environment-scoped -- fires only where this repository's own hook harness is loaded (confirmed by its own matcher, item 3) |
| `gate_acm_issue_disclosure.py` | 3 (CI/CD) | Environment-independent -- fires on the `issues` webhook regardless of which client created the issue (item 18) |

The gate script's own docstring states the rationale for needing all
three explicitly (quoted in full at item 18): the skill trigger alone is
probabilistic, the hook alone is environment-scoped, so only the CI/CD
gate closes the "created via a different client entirely" gap. This is
**deliberate, argued, three-domain coverage** -- the model for what a
"good" Reproducibility score looks like.

### Two counter-examples: real, currently-unargued single-domain coverage

Contrast, found directly in this session's own research, not invented
to fill out the table:

- **Install/`gh`-CLI safety** (items 2, 6): realized in Domain 2 only,
  twice over (`hooks/check-bash-safety.sh` for the main thread,
  `check_task_bash_safety.sh` for task-agent dispatch) -- but with
  **no Domain-3 backstop**. If the same install/`gh`-write policy needed
  enforcing against a change made through a non-Claude-Code path (a
  direct push, a different tool), nothing in this repository's own
  `.github/scripts/` catches it. This report does not know whether that
  gap is deliberate (accepted, since the policy is about *live agent
  action*, not repository *state*) or simply unconsidered -- named as an
  open question below, not resolved here.
- **Retrospective identity** (items 14-17): the *design-only* material
  proposes multi-domain coverage (a Domain-2 issue-creation-time hook
  plus a Domain-3 CI backstop, per item 14's Case C), but what actually
  *shipped* (`post_merge_retro.py`, `scan_retrospective_gate_drift.py`,
  item 15-16) is Domain-3 only -- no Domain-2 hook exists today gating
  retrospective-identity-adjacent actions in a live session. The
  *proposed* architecture had multi-domain coverage as an explicit,
  argued design goal; the *shipped* reality does not yet have it.

### Candidate checks

- **Domain-count disclosure.** Does a gate's own documentation state, or
  can a reviewer determine, how many domains realize the same policy --
  one or several -- rather than assuming single-domain coverage is
  either always sufficient or always insufficient without checking?
- **Argued vs. accidental coverage.** Where multiple domains realize the
  same policy, does something (a docstring, a design doc, a registry
  entry) state *why* -- defense-in-depth against a specific named
  failure mode, layered coverage at different pipeline stages, a
  credential/reversibility asymmetry between layers -- per the six
  criteria in
  [Mechanism-fit](#mechanism-fit-which-domain-should-own-a-policy)
  below, rather than the multiplicity being an unexplained accident of
  history?
- **Single source of truth for the policy's own identity.** Grounded in
  item 14's central principle (quoted in the Guiding principle section):
  where a policy needs the same predicate evaluated in multiple domains
  (e.g., "is this an ACM-exempt chore issue," "is this a retrospective
  issue"), is that predicate defined once and imported, or re-derived
  independently in each realization -- risking exactly the kind of
  silent drift the four-way ACM-regex duplication (item 3) already
  accepts as a known, test-gated risk rather than an unmanaged one?
- **Reversibility-driven placement, not just presence.** Per item 14's
  Criterion 1 (quoted in full under Mechanism-fit below): where a Domain
  2 realization exists specifically because CI-time detection would
  already be too late (the guarded action is irreversible by the time a
  CI job could see it), does the gate's own documentation say so, rather
  than leaving the reader to guess why the same policy is not simply a
  CI/CD gate alone?

## Mechanism-fit: which domain should own a policy?

Not invented for this report -- reused directly from the six criteria
`docs/superpowers/specs/2026-07-18-cicd-gate-cluster-design.md` already
argues from, case by case, across its own gate-placement decisions (item
14 above), generalized here from "hook vs. CI" to "which of the four
domains":

1. **Reversibility window.** Place the check at the earliest domain
   where the wrong action is still cheaply reversible; a domain that
   only sees the damage after it is already irreversible is too late,
   regardless of how clean its own implementation would be (design doc
   lines 238-262, quoted at item 14).
2. **Capability match.** A domain that cannot perform the I/O a check
   needs (e.g., a live remote lookup) cannot own that check, independent
   of timing (same passage).
3. **Credential/trust asymmetry.** Pair an earlier, lower-credential
   domain that can fail open (nothing irreversible happens yet) with a
   later domain that has guaranteed credentials and can fail closed as
   the backstop (design doc lines 250-254).
4. **Tool-surface availability.** Place the check at whichever domain
   actually has a chokepoint for the guarded action -- if only one
   domain exposes the relevant tool call at all, the choice is not
   really a choice (design doc lines 220-224).
5. **Precedent reuse, adapted for local constraints.** Prefer a
   placement a comparable, already-battle-tested gate already uses
   elsewhere (in this repository, or -- per item 17's caveat -- in the
   sibling repository, attributed rather than independently confirmed),
   adjusted for constraints the precedent's own origin did not have
   (design doc lines 172-231).
6. **Prose-rule-to-gate mapping, by action kind.** Rules about *live
   agent-session actions* map to Domain 2 (hooks); rules about
   *repository/file state* map to Domain 3 (CI + pre-commit), since they
   do not require an active session to evaluate; rules about *aggregate,
   noisy signals over time* map to scheduled/advisory CI only,
   deliberately non-blocking (design doc lines 372-436, synthesis).

Two additional, named-but-secondary criteria from the same source:
**zero-I/O gates are structurally safer** (a pure local predicate has no
INDETERMINATE state to fail open or closed on at all -- design doc lines
248-249), and **staged rollout** (a new gate can start advisory and be
promoted to blocking once proven clean, rather than the placement
decision being binary from day one -- design doc line 365).

**What this framework does not cover, named explicitly rather than
silently assumed solved:** the design doc never states a general
principle for "does this policy need a Domain-3 backstop because Domain
2 is Claude-Code-specific and a different client could bypass it
entirely" (confirmed absent by a full-text search this session, item
14) -- the property exists incidentally in one gate (the ACM
worked-example's Case C-equivalent) but is argued there on
credential/reversibility grounds, not client-independence grounds. A
future rubric applying this framework needs its own position on
client-independence as a first-class criterion, not an assumption that
criteria 1-6 already cover it.

## Top-down model, bottom-up discovery

Named explicitly, at the requester's own prompting, rather than left as
an unstated tension: **this evaluation model is being finalized
top-down, in this research pass, before further gate implementation
work proceeds** -- the requester's own stated reason for prioritizing it
this way. That does not mean every future gate must originate top-down.
This repository already has a proven, working **bottom-up** mechanism
for *discovering* which gates are needed: `merge-retrospective` and
`scan_retrospective_gate_drift.py`'s own history (item 16) -- a proposal
sits unbuilt until repeated real incidents make the pain concrete enough
to justify building it. `gate_skill_audit_disclosure.py` and
`gate_skill_rename_lifecycle.py` (item 20) also cite specific incident
issue numbers in their own headers, the same pattern --
`scan_apm_manifest_drift.py` is the one gate among those inventoried
that does not (item 20's own outlier), framed instead around a standing
invariant with no incident cited.

This model does not replace that discovery mechanism. It is positioned
as **the yardstick applied once a gate (however discovered) is being
judged for quality** -- top-down in the sense that the yardstick itself
is fixed now, not in the sense that every gate it measures must have
been designed top-down. A gate born from three repeated incidents
(bottom-up discovery) and a gate born from a comprehensive design doc
(top-down design, item 14) are graded by the same model once built; the
model has no opinion on which origin story is better, only on whether
the resulting artifact is reproducible, thin, environment-appropriate,
and honestly scoped.

### Precedent from manufacturing and logistics

Researched at the requester's own direction, to back the
top-down-model-first sequencing above with established industrial-
engineering doctrine rather than leaving it as an unsupported analogy.

**Sourcing tier, stated upfront rather than left implicit:** this
session's outbound network policy blocked direct `WebFetch`/`curl`
access to every external source below (`global.toyota`, `lean.org`,
`deming.org`, MIT Press, Wikipedia, `archive.org`) -- the same
allowlist-driven pattern already disclosed for Devin and Cursor
elsewhere in this report. Every quote in this subsection was obtained
through `WebSearch` result synthesis, not a byte-level page fetch this
session could independently verify character-for-character or pin to
an exact page number. This is a **weaker evidentiary tier** than the
rest of this report's citations, per this session's own
`grounding-in-primary-sources` discipline -- treat the quotes below as
well-corroborated (independently returned by multiple searches, in
each case) rather than as fully agent-verified primary-source fact.

- **Jidoka (自働化).** Toyota Motor Corporation's own official global
  site (per `WebSearch` synthesis, not independently fetched):
  "Jidoka -- which can be loosely translated as 'automation with a
  human touch' -- is based on the concepts of stopping immediately when
  abnormalities are detected to prevent defective products from being
  produced..." (the source continues: "and improving productivity to
  eliminate the need for people to be simply watching over machines").
  Named one of TPS's two pillars alongside Just-in-Time.
  This is, in a manufacturing vocabulary, close to a direct restatement
  of what this report already calls a deterministic gate: a mechanism
  that halts a bad outcome the instant it is detected, rather than
  letting it propagate and relying on downstream inspection (or model
  judgment) to catch it later.
- **Poka-yoke (mistake-proofing).** Shigeo Shingo, in the work that
  formalized the concept (via a secondary reproduction of his own
  words, `Zero Quality Control: Source Inspection and the Poka-Yoke
  System`, Productivity Press, 1986): "mistakes will not turn into
  defects if worker errors are discovered and eliminated beforehand" --
  devices and process designs engineered to catch or prevent an error
  at its source, rather than relying on vigilance after the fact.
- **Standardized work as the precondition for kaizen, with an
  important nuance.** The popular aphorism "where there is no standard,
  there can be no kaizen," widely attributed to Taiichi Ohno, could not
  be traced this session to a page-cited original sentence -- flagged
  explicitly as Speculation, not asserted as a verified quote. A
  citable substitute, from the same tradition: "The standard is only
  the baseline for doing further kaizen" (Taiichi Ohno, *Taiichi Ohno's
  Workplace Management*, trans. Jon Miller, Gemba Press / McGraw-Hill).
  **The more load-bearing finding is a nuance, not the aphorism itself:
  Toyota's own doctrine is not purely top-down.** System-level design --
  that a process halts immediately on any detected abnormality, as a
  non-negotiable standard -- is a management/engineering decision, made
  top-down. But the *specific* poka-yoke devices and stopping mechanisms
  that satisfy that standard are documented as routinely proposed
  bottom-up, by shop-floor workers, through kaizen and Toyota's own
  suggestion system, operating *inside* the standard the top-down
  decision already fixed. This maps directly onto the position already
  taken above: the evaluation *model* (the standard -- what "good" means,
  fixed now) is top-down; *which specific gates* satisfy it can still be
  discovered bottom-up (`scan_retrospective_gate_drift.py`'s own
  incident-driven origin, item 16, is this repository's own instance of
  exactly this pattern, independently arrived at before this
  manufacturing precedent was researched).
- **Deming's statistical process control.** W. Edwards Deming, *Out of
  the Crisis* (MIT Center for Advanced Engineering Study, 1986),
  Chapter 11 (page not independently confirmed this session): "Without
  statistical control, the process was in unstable chaos, the noise of
  which would mask the effect of any attempt to bring improvement." A
  process must first be brought into a stable, standardized state before
  any change in its output can be attributed to a real improvement
  rather than noise -- the same load-bearing idea as standardized work,
  from a different tradition.
- **Logistics: the control-tower pattern.** DHL's own glossary: "A
  control tower is a central hub offering end-to-end supply chain
  visibility and real-time analytics to manage logistics performance
  and control costs." IBM's own materials describe a control tower
  replacing a prior state
  where supply-chain data was "scattered across organizational silos,"
  each node keeping its own copy, out of sync with the others. This is
  the same "single source of truth, imported not re-derived" principle
  this report's own Guiding principle section already grounds in
  `docs/superpowers/specs/2026-07-18-cicd-gate-cluster-design.md`
  (item 14) -- found independently in a different industry's own
  vocabulary, not introduced here for the first time.

**Synthesis, this report's own, not a quote:** across three independent
traditions (Toyota's TPS, Deming's SPC, logistics control-tower design),
the same shape recurs -- a fixed, top-down-set standard or single source
of truth is what makes local variation *measurable and correctable* in
the first place, while the specific mechanisms satisfying that standard
are routinely improved or discovered bottom-up, inside the boundary the
standard fixes. This is offered as corroborating precedent for
finalizing the evaluation model now, before further gate implementation
-- not as proof the requester's own principle was derived from these
sources, and not as license to treat every future gate's own design as
needing top-down authorship.

### Decision-derivation logic for the standard itself

A gap the requester's own follow-up question named precisely: the
material above corroborates *that* a top-down-set standard is a
recognized pattern; it does not supply the *decision-making logic* by
which such a standard should itself be derived. Two findings, of very
different evidentiary strength.

**Candidate Lean vocabulary for this, sourced far more weakly than
anything else in this report -- disclosed in full rather than
downgraded quietly.** Researched this session: Hoshin Kanri (policy
deployment) and its "catchball" process, Toyota-lineage Lean's own
answer to "how is a cascading standard actually derived, and by whom."
This session's outbound network policy blocked `WebFetch` **for every
single domain attempted this time, confirmed at the proxy/gateway level
as a policy denial, not a partial or domain-specific block** -- a
strictly worse access state than the manufacturing/logistics research
above, which at least corroborated wording across repeated independent
searches. No claim below should be read as a verified quote; none of
it could be checked against a primary text (Yoji Akao's own book,
*Hoshin Kanri: Policy Deployment for Successful TQM*, was unreachable
in every attempted form). Even surface facts conflict across sources
found this session -- Bridgestone Tire Corporation's founding study is
dated 1965 by some search results and 1968 by others; Akao's own book
is dated 1988, 1989, or 1991 depending on source. **Everything in this
paragraph is Speculation, not Fact, per this session's own
`grounding-in-primary-sources` discipline**, offered only because the
underlying *concept* -- a target proposed top-down is met with a
feasibility/means counter-proposal from below, negotiated iteratively
("tossed back and forth like a ball") until both sides agree, *before*
the standard is finalized, explicitly distinct from either pure
top-down dictation or pure bottom-up aggregation -- is coherent and
useful vocabulary even where this session could not pin down a citable
sentence for it.

**The stronger finding: this session's own conduct, fully verifiable
because it requires no external source at all.** The Guiding principle
above was not, in fact, derived by pure top-down dictation. Read back
what actually happened, in order: earlier rounds of this same session
(the agent-tool compatibility axis, dependent middleware) already
established a working pattern of proposal-then-grounding-check before
anything was accepted; when the requester then stated the Guiding
principle's own candidate wording specifically, this report checked it
against this repository's own internal precedent (the audit-trail and
CI/CD design docs) for convergence *before* accepting it as the model's
own Decision; the requester then posed further questions of the
finalized model itself (the Lean/manufacturing grounding request, this
very derivation-logic question) that were answered by further grounding
passes, each of which fed back into revising the report; several rounds
of adversarial verification then caught and forced correction of
specific overclaims the model-in-progress had made. That sequence -- a
proposed standard, a feasibility/convergence check against what already
exists, negotiation through further questions and corrections, repeated
until both sides hold -- **is
catchball's own described shape, independent of whether this report's
weakly-sourced citations for the term itself hold up.** This report
does not need the Hoshin Kanri citations to be strong for this
conclusion to stand: the decision-derivation logic actually used to
reach the Guiding principle above is observable directly in this
session's own history, not asserted from an unverifiable external
source.

**What this means as the report's own answer to "how is the standard's
own derivation logic handled":** not by the requester's authority
alone, and not by this report's own research alone, but by iterating
the two against each other -- a proposed standard is only finalized
once it survives being checked against existing precedent and
challenged by further questions, the same shape Lean's own catchball
concept describes for cascading a standard through an organization,
applied here to deriving one at all.

## Candidate quality dimensions (research proposal, not a shipped rubric)

Modeled on `evaluating-skill-quality`'s own two-lane split. Derived from
Domain-2 (hook) research specifically -- generalizing every dimension to
Domains 3-4 explicitly is future work, not completed in this pass (see
[Open questions](#open-questions--blind-spots)). Every dimension below
is a candidate for a future rubric to accept, reject, or refine -- none
of these are enforced anywhere yet.

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
15. **Stdout hygiene: nothing but the intended JSON reaches stdout.**
    Grounded in Gemini CLI's own documented rule ("Silence is Mandatory
    ... Even a single `echo` or `print` call before the JSON will break
    parsing") and, independently, Claude Code's own hooks-guide
    troubleshooting entry for the identical failure mode (a shell profile's
    unconditional `echo` corrupting a hook's JSON output, in the Dependent
    middleware section above) -- two independently-designed tools naming
    the same concrete risk is stronger evidence than either alone that
    this is a real, not hypothetical, failure mode. Does a hook's own
    script route every diagnostic/log line to stderr, leaving stdout for
    the final JSON only?
16. **Fail-closed default on incomplete or malformed input.** Grounded in
    OpenClaw's own stated principle ("Missing fields are unproven, not
    false assurances; fail closed when policy requires them"), which
    independently converges with this repository's own
    `zero-trust-threat-model.md` ("fail closed, including on
    INDETERMINATE" -- zero-trust principle 6, item 21 above). Does a
    hook's own script default to deny (or escalate) when its input is
    malformed, a field it depends on is missing, or a script/binary it
    shells out to is absent -- rather than silently defaulting to allow?
    This repository's own `check-issue-acm-disclosure.sh` already gets
    this right (confirmed directly in `hooks/check-issue-acm-disclosure.
    sh:54-56`: it denies, with a named reason, if its own companion
    `check_acm_present_or_waiver.py` is not found -- a behavior item 3
    above does not itself narrate, so cite the script directly rather
    than that item) -- a rubric could make this an explicit, checkable
    expectation rather than an incidental property of the scripts that
    happen to have it.
17. **Runtime tamper-*detection* awareness of a hook's own definition,
    distinct from review-time screening -- and distinct from
    tamper-*prevention*, a stronger property this report does not claim
    exists anywhere.** This repository already hard-flags a hook/script
    diff at review time (`screening-a-low-trust-contribution` check 4,
    item 10 above) -- a human/agent gate on an *incoming PR*. Gemini
    CLI's own documented mechanism is a different, complementary layer
    operating at a different time: it fingerprints a project-level
    hook's own name/command and warns when a change is detected (e.g.
    via `git pull`), though per its own documented flow the hook still
    executes by default after that warning, unless a separate security
    setting blocks it -- detection and warning, not a re-approval gate.
    This repository has no analogous *runtime* check today -- review-time
    screening catches an incoming PR; it says nothing about a hook
    definition changing through any other path (a later commit an
    earlier review already passed, a local edit, a plugin update). A
    rubric could name this gap explicitly rather than treating
    review-time screening as complete coverage on its own.
18. **Discoverability: a hook's existence and purpose is not silent
    magic.** Grounded in HermesAgent's own recounted design mistake and
    its fix -- an earlier version "silently spawned an agent with bare
    defaults on every gateway boot," which "surprised users"; the fix
    was requiring the behavior to be "a documented pattern... built by
    you, in your hooks directory," so "you see exactly what it does and
    opt in by writing the files." This repository's own shipped hooks
    already mostly satisfy this independently, though not uniformly --
    `hooks/hooks.json`'s own top-level `description` field and three of
    the four hook scripts (`check-bash-safety.sh`,
    `check-issue-acm-disclosure.sh`,
    `check_task_bash_safety.sh`) name the specific finding, issue, or
    design-doc decision each backs in a header comment; the fourth,
    `hooks/check-template-overwrite.sh`, has a header comment describing
    what it does but names no specific backing finding or issue number
    -- the same script this report's own item 4/5 already flagged as an
    exception on a different property (no bundled test file). A rubric
    could make citing a specific backing decision an explicit, checkable
    expectation -- a hook whose own comment states only what it does,
    never why or on whose authority -- rather than treating this
    repository's own mostly-consistent practice as already complete.

## Open questions / blind spots

Per this repository's own Unknowns framework (`evaluating-skill-quality`'s
Blind spot pass), named explicitly rather than left implicit:

- **`tvna/claude-md` (the sibling) was never independently verified this
  session.** Three `add_repo` attempts each returned "MCP tool call
  requires approval" without resolving. Everything this report says
  about the sibling's own gate cluster, its incident-driven history
  (implied by "incident #1395" and similar citations inside gitapex's
  own design doc), or its bottom-up-vs-top-down development style is
  *attributed to gitapex's own citations of it*, not independently read.
  This is the single largest unverified claim class in this report --
  named here explicitly, not smoothed over by the volume of indirect
  evidence gathered instead.
- **Dimensions 1-18 above were derived from Domain 2 research and have
  not been re-derived for Domains 3 or 4.** Some generalize immediately
  (fail-closed defaults, middleware disclosure); others may not transfer
  cleanly (e.g., "exit code 2" is Domain-2-specific vocabulary with no
  obvious Domain-3 or Domain-4 analogue argued in this report). A future
  pass should re-walk each dimension against Domain 3's own real
  artifacts (item 14-20) and Domain 4's thin ones, rather than assuming
  Domain-2 language ports unchanged.
- **The Reproducibility axis's own worked examples (ACM: 3 domains;
  install-safety: 1 domain with no argued gap-acceptance; retrospective:
  proposed multi-domain, shipped single-domain) were not battle-tested
  against a case this report did not already know about.** Whether the
  axis actually surfaces new gaps on a policy this report has not yet
  looked at is untested.
- **No behavioral-evidence convention exists for gates the way it does
  for skills.** `evaluating-skill-quality` dimension 8 asks for an eval
  suite and a no-skill baseline; no `evals/*/eval.yaml` precedent exists
  for a *gate* today (the closest is
  `evals/screening-a-low-trust-contribution/tasks/hook-script-change.yaml`,
  which tests contribution screening, not a gate's own correctness).
- **The `prompt`/`agent` hook-type question (dimension 8) is unresolved,
  not just unaddressed.** This report surfaces it as a real design fork,
  not a settled position.
- **This report's own external-source coverage has several unverified
  cross-checks**: the plugin-shipped-agent hooks restriction (External
  sources list above), Devin's own hook mechanism (proxy-blocked,
  `docs.devin.ai`), Cursor's (proxy-blocked, `cursor.com`/
  `docs.cursor.com`) -- named rather than silently presented as
  independently confirmed.
- **The entire "Precedent from manufacturing and logistics" subsection
  rests on a weaker evidentiary tier than the rest of this report.**
  This session's network policy blocked direct `WebFetch` access to
  every source cited there (Toyota's own site, Shingo, Ohno, Deming,
  DHL, IBM); every quote came from `WebSearch` synthesis, not an
  independently fetched and read page. The quotes are well-corroborated
  (consistent across repeated searches) but not agent-verified the way
  this report's other citations are -- named explicitly in that
  subsection itself, and repeated here per this report's own Unknowns
  framework.
- **The Hoshin Kanri / catchball material in "Decision-derivation logic
  for the standard itself" is sourced weaker still -- Speculation, not
  Fact, explicitly.** This session's `WebFetch` was blocked for every
  domain attempted (a session-wide policy denial, confirmed at the
  proxy level), not merely the partial block the manufacturing/
  logistics subsection hit. No quote there could be checked against a
  primary text, and even basic facts (Bridgestone's founding-study
  date, Akao's own book's publication year) conflict across sources.
  The section's own load-bearing conclusion does not depend on this
  material holding up -- it rests instead on this session's own directly
  observable conduct -- but the Hoshin Kanri vocabulary itself should
  not be cited onward from this report as verified.
- **Whether a deterministic-gate-quality skill should be a new skill at
  all, versus an extension of `screening-a-low-trust-contribution` check
  4 (which already hard-flags any hook/script diff) or a new dimension
  bolted onto `evaluating-skill-quality` itself**, is an open
  mechanism-fit question this report does not resolve -- see
  [Next steps](#next-steps-decision-ready-options).
- **The design-only future architecture (items 21-22) and the shipped
  reality (items 1-20) are evaluated by this report as if they will
  eventually need the same model, but that is this report's own
  assumption, not a decision the requester has made.** Whether the
  eventual Rego-based engine changes what "good" means for a gate (e.g.,
  making Domain-coverage automatic rather than something each gate
  author argues for individually) is unexamined.

## Explicitly out of scope for this pass

- No `skills/evaluating-deterministic-gate-quality/` directory,
  `SKILL.md`, rubric, or shape checker is created by this report.
- No changes to `hooks/hooks.json`, any existing hook script, or any
  `.github/scripts/` gate.
- No eval suite is created for the candidate dimensions above; none of
  them have been battle-tested against a real gate contribution yet.
- No `references/runtime-compatibility.md`-equivalent baseline document
  is created for gates in this pass; the Compatibility awareness section
  above is this report's own inline research, not a maintained,
  separately-versioned baseline file the way the skill-side rubric has.
- Dimensions 1-18 are not re-derived for Domains 3-4 in this pass (named
  explicitly above, not silently assumed complete).
- `tvna/claude-md` is not independently read in this pass (access
  blocked; named explicitly above).

## Redistribution requirements for the eventual skill

Per the requester's own framing of gitapex's mission: "CLI proxy and
agentic skills for git effectively workflow optimization serving as an
apex operational weapon for rapid issue and pull request triage,
autonomous bug repair, and layered Git defense." gitapex's own reason
to exist is to be redistributed and used to harden *other*
repositories' git workflows, not only gitapex's own. Every worked
example in this report (items 1-22 above) audits gitapex's own gates;
the eventual skill has to work when auditing an adopter's gates
instead, or it fails that stated mission on its first real use.

### What actually gets redistributed, confirmed by primary source

Fact, per `docs/repository-layout.md` (read this session): "Only
skills (and, later, hooks) are deployed as runtime primitives;
everything else -- contributor instructions..., CI tooling, tests, and
docs -- is carried in the repository for development but is never
deployed into a consumer's agent." Its own layout table states
explicitly: `.github/` ("CI workflows and their internal tooling...
-- not deployed"), `docs/` ("not deployed"), `tests/` ("not
deployed"); only `skills/` is confirmed deployed by apm/Claude/Codex,
with `hooks/` deployment described in that same sentence as "in the
future" for **apm's own discovery mechanism specifically** --
separately, Claude Code's own native plugin-hook loading already reads
`hooks/hooks.json` today (confirmed by `hooks.json`'s own working
`$CLAUDE_PLUGIN_ROOT`-relative paths, exercised throughout this
report's Domain-2 research), so hooks already travel with the plugin
through that channel even where apm's own discovery of them remains
pending -- this report does not conflate the two distribution paths.

**Consequence, stated plainly:** items 14-22 -- the entire CI/CD gate
cluster case study, the entire design-only future-architecture
material, and this report itself -- live under `docs/` or effectively
document `.github/`, **none of which ever reaches a consumer
repository that installs gitapex as a plugin.** A future
`evaluating-deterministic-gate-quality` skill's own bundled content is
the only part of this research that will ever travel with gitapex once
redistributed. Citing this report by path from inside the skill ("see
`docs/superpowers/reports/...`") would be exactly the portability
failure `evaluating-skill-quality`'s own rubric already names and
prohibits (a reference the *procedure* depends on to function, outside
the skill's own folder, fails Portable) -- any finding here the
eventual skill actually needs at runtime must be copied into the
skill's own `references/`, not left as a pointer into gitapex's own
dev-only tree.

### Division of responsibility: the skill vs. the gitapex single binary

Correction from the requester, folded in explicitly rather than left as
an implicit tension in the section above: the redistribution gap just
named -- Domains 1, 3, and 4 enforcement not traveling with the Claude
Code plugin's `skills`/`hooks` channel -- **is not a problem the
eventual skill needs to solve.** It is gitapex's own design-only
single-binary architecture's stated responsibility (items 21-22 above):
"a single static binary CLI (Rust provisional/Go later)... REDISTRIBUTED:
independent organizations run their own copy against their own repos,
with their own adopter-authored `.rego` policy files" -- a *separate*
redistributed artifact from the Claude Code plugin, installed and run
independently, whose entire reason to exist already matches the guiding
principle above: one policy schema, evaluated identically regardless of
which of the four domains invokes it. That binary, once built, is the
mechanism that loosely couples to whatever's environment-optimal and
guarantees reproducibility across domains -- not the Claude-Code-native
skill; the skill and the single binary are two separate redistributed
artifacts with two separate scopes, not one artifact wearing two hats.

This resets the eventual skill's own proper scope, narrower than the
previous section's own wording might otherwise suggest: it is a
Domain-2-native artifact, carried by the channel that actually
redistributes it (the plugin's `skills`/`hooks`), and its job is to
*grade* whatever deterministic-gate artifacts a target repository
already has -- including Domain-1/3/4 ones, read for audit purposes, if
the target repo happens to have them -- not to *become* the mechanism
that redistributes cross-domain enforcement itself. Auditing a target's
existing Domain-3 CI config or Domain-4 MCP config is a much smaller
task than being the thing that makes such enforcement reproducible
across environments in the first place; that larger task belongs to
the single binary, once it exists, not to this skill.

### Portability level the eventual skill must declare, and why it is Mixed

The eventual skill is itself a skill, so it is subject to
`evaluating-skill-quality`'s own axis, not exempt from it because it
happens to grade other artifacts. Per that rubric's own three-way
split (read this session): "**Mixed**: a portable core plus
repo-specific detail should split the two into a clearly named
reference file, not blend them." This report's own material already
sorts cleanly into that split:

- **Portable core** (belongs in the skill's own `SKILL.md`/bundled
  `references/`, travels with every install): the Guiding principle,
  the four-domain taxonomy (git hooks / agent-harness hooks / CI job /
  MCP server), the two-lane structure, the Reproducibility axis's
  *concept*, and the six mechanism-fit criteria -- none of these name a
  gitapex-specific file path or issue number in their own statement.
- **Repository-scoped detail** (gitapex's own worked examples only,
  must not be assumed present in a target repo): the ACM-disclosure
  three-domain case study, the OWASP-mapping ports from
  `tvna/claude-md`, the retrospective-identity bottom-up-origin story,
  and every specific script name (`gate_acm_issue_disclosure.py`,
  `hooks/check-bash-safety.sh`) cited throughout items 1-22.

`screening-a-low-trust-contribution`'s own already-established
convention for exactly this split (read this session) is the direct
precedent to follow, not a new pattern to invent: "This skill's checks
are general categories. The specific paths named below
(`.github/workflows/**`, `hooks/**`, `pyproject.toml`/`uv.lock`) are
gitapex's own illustrative examples of each category -- substitute the
calling repository's actual equivalents." The eventual gate-quality
skill needs the same discipline: name domains and criteria
generically, illustrate each with gitapex's own example *labeled as an
example*, and instruct the invoking session to discover the target
repository's own actual realizations rather than assuming gitapex's
own paths exist there.

### Candidate specification points for the eventual skill's own build

- **Discovery step, not hardcoded paths -- for grading, not for
  building enforcement.** Before grading, the skill must locate the
  target repository's own Domain-2/3/4 artifacts (its own hook config,
  its own CI gate scripts, its own MCP config if any) -- gitapex's own
  layout is one illustrative case, never assumed as the target's shape.
  Per the Division of responsibility above, this discovery step exists
  only to *find what to audit*; it is not the skill's job to supply or
  redistribute the cross-domain enforcement itself where a target lacks
  it -- that gap, if a target repo has one, is out of scope for a
  grading skill and belongs to whatever plays the single-binary role
  for that repository's own ecosystem, not something this skill should
  attempt to fill in.
- **Declare Portable/Mixed, not silently assume Portable.** Per the
  section above, the honest declaration is Mixed -- the skill's own
  shape checker (mirroring `evaluating-skill-quality`'s own
  `check_skill_shape.py`) should fail closed if a future edit blends
  repo-specific gitapex detail back into the portable core.
- **The Reproducibility axis's own worked-example table must be
  replaced per target, not reused.** The ACM/install-safety/
  retrospective-identity table in this report is gitapex's own
  evidence; a target repository's own policy-to-domain coverage table
  has to be built fresh from that repository's own artifacts,
  following the same method, not copied from this report.
- **Serves gitapex's own stated mission directly, not incidentally.**
  Per the requester's own framing of gitapex as an "apex operational
  weapon for rapid issue and pull request triage, autonomous bug
  repair, and layered Git defense" -- deployed into adopter repos, not
  used only on itself -- a gate-quality skill that only works when
  auditing gitapex's own gates fails that mission on its first real
  use. This is not a nice-to-have generalization; it is the specific
  reason this skill needs to exist as a redistributable artifact at
  all, per gitapex's own reason for existing.

## Next steps (decision-ready options)

Per this repository's own "never hand a human a decision that is not
decision-ready" convention, four concrete, named options for whoever
picks up this research next -- not an open-ended "what should we do":

- **(a) Build a new `evaluating-deterministic-gate-quality` skill now**,
  using this report's model as-is: the guiding principle, the four-domain
  taxonomy, the two-lane split, three axes (Compatibility awareness,
  Reproducibility/Domain-coverage, Blast-radius), and the six-criterion
  mechanism-fit test, with dimensions 1-18 generalized from Domain 2 to
  all four domains as part of the build itself, and built Mixed from the
  start per
  [Redistribution requirements](#redistribution-requirements-for-the-eventual-skill)
  above -- portable core in `SKILL.md`, gitapex's own worked examples
  moved into a clearly named, explicitly repo-scoped reference file
  rather than left inline.
- **(b) Retry `tvna/claude-md` access first**, then build (a) -- since
  the sibling's own gate cluster is this repository's single richest
  precedent for multi-domain, incident-driven gate design and is
  currently only known second-hand.
- **(c) Resolve the `prompt`/`agent` hook-type mechanism-fit question
  first**, as its own small design spike, before generalizing dimension
  8 to the other three domains, since it changes what "deterministic"
  even means once a domain's own hook-equivalent mechanism supports a
  judgment-calling variant (Domain 2's `prompt`/`agent` hooks; an
  analogous question may exist for Domain 3 CI steps that call an LLM,
  or Domain 4 MCP tools that do the same).
- **(d) A narrower step**: extend `screening-a-low-trust-contribution`
  check 4 (currently a hard-flag-and-nothing-more, Domain-2-scoped) into
  a fuller, cross-domain checklist using the deterministic-shape checks
  above, without building a whole new sibling skill yet -- deferring the
  probabilistic-maturity, Compatibility-awareness, and Reproducibility
  dimensions to a later pass once (a)/(b)/(c) above are picked.

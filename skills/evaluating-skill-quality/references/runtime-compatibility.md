# Runtime compatibility baseline

Snapshot date: 2026-07-27.

This is an evidence baseline for the warning-only compatibility-awareness
axis. It is not an enforcement adapter and does not claim that a runtime
rejects every undocumented field. Product documentation changes; refresh the
relevant row before making a current behavior claim.

In this repository (gitapex), this baseline is one of four distinct
"which agent products does GitApex support" questions the repository
answers differently; see
[agent-product-scope.md](../../../docs/agent-product-scope.md) (Axis C)
for how it relates to the plugin-distribution target and the
enforcement-adapter target set. Growing this baseline's runtime list
does not change either of those.

## Contents

1. [Standard baseline](#standard-baseline)
2. [Runtime matrix](#runtime-matrix)
3. [Primary sources](#primary-sources)
4. [Review rules](#review-rules)

## Standard baseline

The [Agent Skills specification](https://agentskills.io/specification)
defines these `SKILL.md` frontmatter fields:

- required: `name`, `description`;
- optional: `license`, `compatibility`, `metadata`;
- experimental optional: `allowed-tools`.

`compatibility` is a 1-500 character string for intended products,
environment requirements, system packages, or network access. `metadata` is
a standard extension container whose standard value shape is a map from
string keys to string values; nested maps are runtime extensions even though
the top-level key is standard. `allowed-tools` support is explicitly
experimental and may vary between implementations.

Classification uses three evidence states:

- **Documented**: the linked primary source states the behavior.
- **Unknown**: the primary source does not establish the behavior. Absence
  from documentation is not evidence that the runtime rejects it.
- **Conflict**: two documented runtimes assign materially different
  semantics to the same construct.

## Runtime matrix

| Runtime | Documented standard relationship | Documented runtime-specific behavior | Unknowns relevant to review |
|---|---|---|---|
| Claude Code | Supports `SKILL.md` plus product-specific frontmatter | `context: fork`, `agent`, and `background` control subagent execution. `allowed-tools` pre-approves tools for the invoking turn and does not restrict other tools; `disallowed-tools` is the product restriction field. Dynamic command substitution runs before skill injection. | The Agent Skills standard does not define the Claude-specific fields or dynamic substitution semantics. |
| Codex | OpenAI states that Skills follow the Agent Skills open standard and are supported in Codex. | No Codex-specific `SKILL.md` frontmatter behavior was established by the public source used for this snapshot. | Treatment of each vendor extension is Unknown unless current Codex documentation or observed runtime behavior establishes it. |
| Gemini CLI | Official documentation says Agent Skills are based on the open standard. | Activation requires consent, injects the body and folder structure, and adds the skill directory to allowed file paths for bundled assets. | The documentation used here does not establish that `compatibility` or `allowed-tools` is enforced. |
| Devin | Official documentation says skills follow the Agent Skills standard. | Devin says `allowed-tools` restricts the active skill to the listed tools; it also adds `argument-hint` and `triggers`, and expands arguments plus command-output substitutions at invocation. | The restrictive Devin meaning conflicts with Claude Code's pre-approval meaning for the same experimental field. Behavior for other vendor extensions is Unknown. |
| Windsurf | Official documentation (a separate page on the same docs.devin.ai site now that Cognition, Devin's maker, owns Windsurf) describes Cascade's skill loading as "progressive disclosure" and links to agentskills.io. | Documents only `name` and `description` as frontmatter fields; no `license`, `compatibility`, `metadata`, or `allowed-tools` is mentioned anywhere on this page. Skills are discovered from `.windsurf/skills/` (workspace) and `~/.codeium/windsurf/skills/` (global, using the legacy Codeium directory name), plus OS-specific read-only Enterprise system paths. The same page states "Devin Desktop also discovers skills in `.agents/skills/` and `~/.agents/skills/`" and, if Claude Code config reading is enabled, `.claude/skills/`/`~/.claude/skills/`. Windsurf documents Skills as one of three distinct mechanisms (Skills / Rules / Workflows); behavioral activation modes (`always_on`/`glob`/`model_decision`/`manual`) belong to Rules, not `SKILL.md` frontmatter. | Whether `license`, `compatibility`, `metadata`, or `allowed-tools` are recognized, silently ignored, or rejected is Unknown -- this page does not establish it. This is a distinct documented product surface from the Devin row above (different page, different frontmatter fields, no restrictive `allowed-tools` claim here); do not conflate the two rows' behavior. |
| OpenClaw | Official documentation says OpenClaw follows the Agent Skills specification. | Product eligibility uses a nested `metadata.openclaw` map, including binary, environment, config, OS, and install hints. This is a non-standard value structure under the standard `metadata` key. Product command fields also exist. | A standard `compatibility` declaration is not documented as enforcing these gates. |
| HermesAgent | Official documentation says the skill system is compatible with the Agent Skills open standard. | Top-level `platforms` hides skills on incompatible operating systems. Hermes-specific tags, categories, toolset requirements, and config use a nested `metadata.hermes` map, a non-standard value structure under the standard `metadata` key. | Behavior for other vendor extensions is Unknown. |
| Kimi CLI | Official MoonshotAI documentation states Kimi CLI loads Agent Skills from a directory containing `SKILL.md` and documents `name`, `description`, `license`, `compatibility`, and `metadata` with the standard shapes. | On startup Kimi CLI injects each skill's name, path, and description into the system prompt; the agent decides whether to read the full `SKILL.md` body. A Kimi-specific `type: flow` value designates a "flow skill" that embeds an Agent Flow diagram for multi-step automation and is invoked with `/flow:<name>` instead of the standard `/skill:<name>`. Tool access is documented as a separate `plugin.json` mechanism; the skills documentation does not mention `allowed-tools`. | The Agent Skills standard does not define `type: flow` or the plugin/skill tool-access split. Behavior if an `allowed-tools` field is present in frontmatter (ignored vs. rejected) is Unknown. |
| Cursor | Official documentation states "Agent Skills is an open standard" and links to agentskills.io. | Cursor auto-discovers skills at startup from `.cursor/skills/` and `.agents/skills/` (both project- and user-level, e.g. `~/.cursor/skills/`), and separately loads `.claude/skills/` and `.codex/skills/` (plus their home-directory equivalents) "for compatibility" with Claude Code and Codex. Its documented frontmatter table lists only `name` (required), `description` (required), a Cursor-specific `paths` field (glob patterns that scope the skill to matching files), a Cursor-specific `disable-model-invocation` field (forces manual-only invocation via `/skill-name`), and `metadata`. Skill directories may nest arbitrarily for organization; identity comes from the immediate folder name, not the category path. Cursor also ships its own built-in skills (e.g. `/create-skill`, `/migrate-to-skills`) that appear alongside user-authored ones. | The documented frontmatter table does not mention `license`, `compatibility`, or the experimental `allowed-tools` field at all; whether Cursor recognizes, silently ignores, or rejects them is Unknown. |
| GitHub Copilot | Official documentation states "The Agent Skills specification is an open standard" and that skills work across Copilot's cloud agent, code review, CLI, GitHub Copilot app, and agent mode in VS Code and JetBrains IDEs. | Documents `name` (required), `description` (required), and `license` (optional). `allowed-tools` is documented as pre-approval, matching Claude Code's meaning and conflicting with Devin's: "list the tools Copilot may use without asking for confirmation each time. If a tool is not listed in the `allowed-tools` field, Copilot will prompt you for permission before using it." Skills are discovered from project `.github/skills`, `.claude/skills`, or `.agents/skills`, and personal `~/.copilot/skills` or `~/.agents/skills` -- directly reading Claude Code's directory alongside its own. | The documentation used here does not mention `compatibility` or `metadata` frontmatter at all; whether they are recognized, silently ignored, or rejected is Unknown. The separate Copilot SDK product documents only `name`/`description` in frontmatter, so its exact field support may differ from the CLI/cloud-agent product this row covers. |
| Kiro | Official AWS documentation states skills "follow the open Agent Skills standard" and links to agentskills.io/specification. | Documents `name`, `description`, `license`, `compatibility`, and `metadata` with the standard shapes; no vendor-specific frontmatter field is documented. Skills are discovered from `.kiro/skills/` (workspace) and `~/.kiro/skills/` (global); a custom agent can also eagerly load specific skills via `skill://` URIs in its `resources` field (Kiro CLI). Kiro documents a separate, Kiro-specific "Steering" mechanism (`always`/`auto`/`fileMatch`/`manual` modes) and "Powers" (MCP-tool bundles) as distinct from Skills, rather than folding that behavior into `SKILL.md` frontmatter. | The documentation does not mention `allowed-tools` at all; whether it is recognized, silently ignored, or rejected is Unknown. |

## Primary sources

- Agent Skills specification:
  <https://agentskills.io/specification>
- Claude Code skills:
  <https://code.claude.com/docs/en/skills>
- OpenAI Skills help:
  <https://help.openai.com/en/articles/20001066>
- Gemini CLI Agent Skills:
  <https://geminicli.com/docs/cli/skills/>
- Devin Skills:
  <https://docs.devin.ai/product-guides/skills>
- Windsurf (Cascade) Skills:
  <https://docs.devin.ai/desktop/cascade/skills>
- OpenClaw Skills:
  <https://github.com/openclaw/openclaw/blob/main/docs/tools/skills.md>
- HermesAgent Skills System:
  <https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md>
- Kimi CLI Agent Skills:
  <https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/customization/skills.md>
- Cursor Agent Skills:
  <https://cursor.com/docs/skills>
- GitHub Copilot agent skills:
  <https://docs.github.com/en/copilot/concepts/agents/about-agent-skills>,
  <https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills>,
  and (Copilot SDK, a separate product from the CLI/cloud-agent docs above)
  <https://github.com/github/copilot-sdk/blob/main/docs/features/skills.md>
- Kiro Agent Skills:
  <https://kiro.dev/docs/skills/> and (CLI-specific `skill://` resource
  loading) <https://kiro.dev/docs/cli/skills/>

## Review rules

1. Compare frontmatter keys and their value shapes with the standard
   baseline. A top-level extension or non-standard value structure is an
   extension, but not automatically defective.
2. Compare behavior claims with the runtime matrix. Warn only when the skill
   relies on documented runtime-specific semantics, a documented conflict,
   or an Unknown it presents as portable fact.
3. Do not infer unsupported behavior from documentation silence. Report
   `Unknown`, identify what must be verified, and keep the warning
   evidence-bounded.
4. Distinguish a standard top-level `metadata` key from its value shape. A
   string-to-string map is standard; a nested runtime namespace is a
   non-standard value structure and can create a runtime dependency.
5. Refresh the source before asserting current support. Record the checked
   date in the review when compatibility is material.

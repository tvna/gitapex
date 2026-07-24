# Runtime compatibility baseline

Snapshot date: 2026-07-25.

This is an evidence baseline for the warning-only compatibility-awareness
axis. It is not an enforcement adapter and does not claim that a runtime
rejects every undocumented field. Product documentation changes; refresh the
relevant row before making a current behavior claim.

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
| OpenClaw | Official documentation says OpenClaw follows the Agent Skills specification. | Product eligibility uses a nested `metadata.openclaw` map, including binary, environment, config, OS, and install hints. This is a non-standard value structure under the standard `metadata` key. Product command fields also exist. | A standard `compatibility` declaration is not documented as enforcing these gates. |
| HermesAgent | Official documentation says the skill system is compatible with the Agent Skills open standard. | Top-level `platforms` hides skills on incompatible operating systems. Hermes-specific tags, categories, toolset requirements, and config use a nested `metadata.hermes` map, a non-standard value structure under the standard `metadata` key. | Behavior for other vendor extensions is Unknown. |

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
- OpenClaw Skills:
  <https://github.com/openclaw/openclaw/blob/main/docs/tools/skills.md>
- HermesAgent Skills System:
  <https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md>

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

"""Token-based classifier backing check_task_bash_safety.sh (issue #1326,
Stage 1). Self-contained duplicate of hooks/gitapex_check_bash_safety.py,
not a shared import -- this repository's own convention (see that
module's sibling shell script header, and
skills/drafting-issues/scripts/gitapex_check_acm_present.py's docstring)
is that no skill shares a scripts/ directory with another, and only
skills/ and hooks/ are deployed with the plugin (docs/repository-layout.md),
so a cross-directory import between them would break for a consumer
checkout that vendors one without the other.

Adapts hooks/gitapex_check_bash_safety.py's tokenizer and rule set (see
that module's own docstring for the full root-cause analysis of the
bypass class both scripts share) but is intentionally stricter in the
same three ways design doc Decision 17 already establishes for this
script's own predecessor:

  - `gh` is denied entirely (any subcommand, including reads) -- design
    doc Decision 7 states task agents "never touch mcp__github__* write
    tools, `gh`, or `git push` directly," not just gh's write
    subcommands, unlike hooks/check-bash-safety.sh's narrower
    write-subcommand-only gh gate (correct for its own main-thread
    scope, where read-only gh use is not forbidden).
  - `git push` is a hard deny here, not hooks/check-bash-safety.sh's
    warn-only outward-artifact-preflight gate -- a task agent has no
    legitimate reason to push at all (design doc Decision 13: worktree
    merge-back is a main-thread-only step).
  - Additional install-verb coverage the sibling script does not carry:
    `npm ci`, `pnpm install`/`pnpm i`, `yarn install`, bare `pnpm`/`yarn`
    (both default to installing every dependency in the lockfile with no
    subcommand at all), curl/wget piped into a shell interpreter, and
    `npx` (always downloads and runs a package on demand).

Known, disclosed limitation (per dimension 9 of
skills/evaluating-deterministic-gate-quality/references/dimensions.md):
carries the identical residual as the sibling module -- verb
reconstruction that never places the tool or verb name as its own
literal token anywhere in the command (string-slice reconstruction of a
fused variable, or an array-literal-assignment indirection) still
evades Stage 1. Full closure requires Stage 2 (execution-boundary
enforcement), tracked separately per #1326's own stated scope boundary.

Deliberately stdlib-only (shlex, re, json).
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from typing import NamedTuple

_SINGLE_OPS = {";", "|", "&", "(", ")", "\n"}
_MULTI_OPS = {"&&", "||"}
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=(.*)$")


class TokenizeError(Exception):
    pass


def _is_dynamic(token: str) -> bool:
    return "$" in token or "`" in token


def _ifs_split(token: str) -> list[str]:
    for marker in ("${IFS}", "$IFS"):
        if marker in token:
            parts = [p for p in token.split(marker) if p]
            if len(parts) > 1:
                return parts
    return [token]


def _split_punct_run(token: str) -> list[str]:
    if token in _MULTI_OPS:
        return [token]
    if token and all(c in _SINGLE_OPS for c in token):
        return list(token)
    return [token]


def tokenize(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        raw_tokens = list(lexer)
    except ValueError as error:
        raise TokenizeError(str(error)) from error

    tokens: list[str] = []
    for raw in raw_tokens:
        for piece in _split_punct_run(raw):
            tokens.extend(_ifs_split(piece))
    return tokens


def segment_tokens(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _SINGLE_OPS or token in _MULTI_OPS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [seg for seg in segments if seg]


def _assigned_literals(tokens: list[str]) -> set[str]:
    values: set[str] = set()
    for token in tokens:
        if _is_dynamic(token):
            continue
        match = _ASSIGN_RE.match(token)
        if match:
            values.add(match.group(1).lower())
    return values


# uv add/remove absent (PR #1323/#1320): declarative, PR-diff-visible.
# `gh` and `git push` are NOT here -- both handled by their own dedicated,
# fully-blanket checks below (any gh subcommand, any git push form),
# stricter than a simple adjacent-verb table could express.
_DENIED_ADJACENT: list[tuple[str, ...]] = [
    ("pip", "install"),
    ("pip3", "install"),
    ("npm", "install"),
    ("npm", "i"),
    ("npm", "ci"),
    ("yarn", "add"),
    ("yarn", "install"),
    ("pnpm", "add"),
    ("pnpm", "install"),
    ("pnpm", "i"),
    ("go", "install"),
    ("brew", "install"),
    ("apt", "install"),
    ("apt-get", "install"),
    ("gem", "install"),
    ("cargo", "install"),
    ("uv", "pip", "install"),
    ("uv", "install"),
    ("plugin", "install"),
]
_DENIED_PHRASES = [" ".join(pattern) for pattern in _DENIED_ADJACENT]

_WATCHED_TOOLS = {
    "pip",
    "pip3",
    "npm",
    "pnpm",
    "yarn",
    "uv",
    "go",
    "brew",
    "apt",
    "apt-get",
    "gem",
    "cargo",
    "plugin",
}
_WATCHED_VERBS = {"install", "i", "ci", "add"}

_BARE_INSTALL_TOOLS = {"pnpm", "yarn"}
_FETCH_EXEC_INTERPRETERS = {"sh", "bash", "zsh", "dash"}


class Verdict(NamedTuple):
    deny: bool
    reason: str


def _rule_a_literal(segments: list[list[str]]) -> str | None:
    for seg in segments:
        literals = [t.lower() for t in seg if not _is_dynamic(t)]
        for pattern in _DENIED_ADJACENT:
            n = len(pattern)
            for i in range(len(literals) - n + 1):
                if tuple(literals[i : i + n]) == pattern:
                    return f"a package/plugin install command matching a denied verb sequence ({'+'.join(pattern)})"
        for literal in literals:
            for phrase in _DENIED_PHRASES:
                if phrase in literal:
                    return f"a Bash argument containing the denied phrase '{phrase}'"
    return None


def _rule_bare_install(segments: list[list[str]]) -> str | None:
    """Bare `pnpm`/`yarn` with no subcommand (or flags only) installs
    every dependency in the lockfile by default, the same as `pnpm
    install`/`yarn install` -- but a positional subcommand (`yarn test`,
    `pnpm run build`) stays allowed."""
    for seg in segments:
        if not seg or _is_dynamic(seg[0]):
            continue
        tool = seg[0].lower()
        if tool not in _BARE_INSTALL_TOOLS:
            continue
        rest = seg[1:]
        if all((not _is_dynamic(t)) and t.startswith("-") for t in rest):
            return f"a bare '{tool}' invocation with no subcommand, which installs every dependency by default"
    return None


def _rule_fetch_exec(segments: list[list[str]]) -> str | None:
    """curl/wget piped directly into a shell interpreter installs and
    runs unreviewed code just as directly as a package-manager verb."""
    for i, seg in enumerate(segments):
        if not seg or _is_dynamic(seg[0]) or seg[0].lower() not in ("curl", "wget"):
            continue
        for later in segments[i + 1 :]:
            if not later:
                continue
            candidate = later[0].lower() if not _is_dynamic(later[0]) else None
            interp_index = 1 if candidate == "sudo" else 0
            if len(later) > interp_index:
                cand = later[interp_index]
                if not _is_dynamic(cand) and cand.lower() in _FETCH_EXEC_INTERPRETERS:
                    return "piping a download directly into a shell interpreter"
            break
    return None


def _rule_npx(segments: list[list[str]]) -> str | None:
    for seg in segments:
        for tok in seg:
            if not _is_dynamic(tok) and tok.lower() == "npx":
                return "npx, which downloads and runs a package on demand"
    return None


def _rule_gh_any(segments: list[list[str]]) -> str | None:
    for seg in segments:
        if not seg:
            continue
        if not _is_dynamic(seg[0]) and seg[0].lower() == "gh":
            return "the gh CLI, not permitted inside a task-level agent (read or write)"
    return None


def _is_git_push_segment(seg: list[str]) -> bool:
    literals = [(t.lower() if not _is_dynamic(t) else None) for t in seg]
    for i, tok in enumerate(literals):
        if tok != "git":
            continue
        j = i + 1
        while j < len(literals):
            # Bound to a local so mypy can narrow it below -- it cannot
            # narrow a repeated `literals[j]` subscript the way it narrows
            # a plain variable.
            candidate = literals[j]
            if candidate is None or not candidate.startswith("-"):
                break
            flag = candidate
            j += 1
            if len(flag) == 2 and "=" not in flag and j < len(literals):
                next_tok = literals[j]
                if next_tok is not None and not next_tok.startswith("-"):
                    j += 1
        if j < len(literals) and literals[j] == "push":
            return True
    return any("git push" in lit for lit in (t.lower() for t in seg if not _is_dynamic(t)))


def _rule_git_push(segments: list[list[str]], assigned: set[str]) -> str | None:
    for seg in segments:
        if _is_git_push_segment(seg):
            return "git push, not permitted inside a task-level agent (worktree merge-back is main-thread-only)"
        if not seg:
            continue
        if _is_dynamic(seg[0]) and "git" in assigned and "push" in assigned:
            return "git push, not permitted inside a task-level agent (worktree merge-back is main-thread-only)"
        if len(seg) > 1 and not _is_dynamic(seg[0]) and seg[0].lower() == "git" and _is_dynamic(seg[1]):
            return "git push, not permitted inside a task-level agent (worktree merge-back is main-thread-only)"
    return None


def _rule_b1a_dynamic_word_same_segment_verb(seg: list[str], verb_set: set[str]) -> bool:
    if not seg or not _is_dynamic(seg[0]):
        return False
    literals = {t.lower() for t in seg[1:] if not _is_dynamic(t)}
    return bool(literals & verb_set)


def _rule_b1b_dynamic_word_assigned_tool_and_verb(seg: list[str], assigned: set[str], verb_set: set[str]) -> bool:
    if not seg or not _is_dynamic(seg[0]):
        return False
    return bool(assigned & _WATCHED_TOOLS) and bool(assigned & verb_set)


def _rule_b2_watched_tool_dynamic_verb_position(seg: list[str]) -> bool:
    if len(seg) < 2:
        return False
    first = seg[0]
    if _is_dynamic(first) or first.lower() not in _WATCHED_TOOLS:
        return False
    return _is_dynamic(seg[1])


def classify(command: str) -> Verdict:
    try:
        tokens = tokenize(command)
    except TokenizeError as error:
        return Verdict(True, f"the command could not be parsed as shell syntax ({error}). Failing closed")

    segments = segment_tokens(tokens)
    assigned = _assigned_literals(tokens)

    literal_hit = _rule_a_literal(segments)
    if literal_hit:
        return Verdict(True, literal_hit)

    bare_install_hit = _rule_bare_install(segments)
    if bare_install_hit:
        return Verdict(True, bare_install_hit)

    fetch_exec_hit = _rule_fetch_exec(segments)
    if fetch_exec_hit:
        return Verdict(True, fetch_exec_hit)

    npx_hit = _rule_npx(segments)
    if npx_hit:
        return Verdict(True, npx_hit)

    gh_hit = _rule_gh_any(segments)
    if gh_hit:
        return Verdict(True, gh_hit)

    git_push_hit = _rule_git_push(segments, assigned)
    if git_push_hit:
        return Verdict(True, git_push_hit)

    for seg in segments:
        if _rule_b1a_dynamic_word_same_segment_verb(seg, _WATCHED_VERBS):
            return Verdict(
                True,
                "a Bash command word is dynamically constructed, alongside a denied verb literally "
                "present in the same command -- rewrite as a plain literal command so it can be checked",
            )
        if _rule_b1b_dynamic_word_assigned_tool_and_verb(seg, assigned, _WATCHED_VERBS):
            return Verdict(
                True,
                "a Bash command word is dynamically constructed from variables whose assigned values "
                "include both a denied tool and a denied verb -- rewrite as a plain literal command",
            )
        if _rule_b2_watched_tool_dynamic_verb_position(seg):
            return Verdict(
                True,
                "a watched tool is invoked with a dynamically constructed subcommand/verb argument -- "
                "rewrite as a plain literal command so it can be checked",
            )

    return Verdict(False, "no denied pattern matched")


def _fail_closed(message: str) -> None:
    print(json.dumps({"decision": "deny", "reason": message}))


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        _fail_closed(f"the tool-call payload on stdin is not valid JSON ({error}). Failing closed")
        return 0
    if not isinstance(payload, dict):
        _fail_closed("the tool-call payload on stdin is not a JSON object. Failing closed")
        return 0

    tool_name = payload.get("tool_name")
    if tool_name is not None and not isinstance(tool_name, str):
        _fail_closed("tool_name in the payload is not a string. Failing closed")
        return 0
    if tool_name != "Bash":
        print(json.dumps({"decision": "allow", "reason": "not a Bash tool call"}))
        return 0

    tool_input = payload.get("tool_input")
    if tool_input is not None and not isinstance(tool_input, dict):
        _fail_closed("tool_input in the payload is not a JSON object. Failing closed")
        return 0
    tool_input = tool_input or {}

    command = tool_input.get("command")
    if command is not None and not isinstance(command, str):
        _fail_closed("tool_input.command in the payload is not a string. Failing closed")
        return 0
    if not command:
        print(json.dumps({"decision": "allow", "reason": "empty command"}))
        return 0

    verdict = classify(command)
    print(json.dumps({"decision": "deny" if verdict.deny else "allow", "reason": verdict.reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

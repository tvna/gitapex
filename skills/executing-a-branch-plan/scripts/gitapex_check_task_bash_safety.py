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

Closed by Step 8 independent review, ninth round (issue #1326), ported
from the sibling module's own fix of the same finding: bash's own
`${NAME:-default}`/`${NAME-default}`/`${NAME:=default}`/`${NAME=default}`
parameter expansion evaluates to the literal DEFAULT text whenever NAME
is unset (or, for the `:`-prefixed forms, empty) -- a zero-assignment
mechanism for embedding literal text directly in a token. Before this
fix, `_rule_b1a_dynamic_word_same_segment_verb`/`_rule_b1b_dynamic_word_
assigned_tool_and_verb`/`_rule_gh_any`/`_rule_git_push` all only ever
looked at a literal token's own text or a referenced variable's assigned
value, never a token's own embedded default-clause text --
`${NEVER_SET:-uv} ${NEVER_SET2:-install} foo` (confirmed via real bash
argv expansion to resolve to a genuine `uv install foo`) and
`${NEVER_SET:-git} ${NEVER_SET2:-push} origin main` needed NO variable
assignment anywhere in the command at all. Closed via
`_default_clause_literal` (an anchored, whole-token extraction), wired
into all four rules above as an additional source of "value" alongside a
referenced variable's own assigned value.

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
_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# Matches the variable name inside `$NAME`/`${NAME`/`${NAME:-default}`-style
# references -- used to confirm a dynamic token actually references a
# specific assigned variable, rather than merely testing whether some
# unrelated assignment anywhere in the whole command happens to look like a
# tool/verb (see _rule_b1b_dynamic_word_assigned_tool_and_verb's docstring).
_VAR_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")

# Matches a token that is EXACTLY one bash `${NAME:-default}`/
# `${NAME-default}`/`${NAME:=default}`/`${NAME=default}` construct
# (anchored) -- captures just the literal DEFAULT text, group 2. See
# _default_clause_literal below. Ported from
# hooks/gitapex_check_bash_safety.py's own fix of the same finding.
_DEFAULT_CLAUSE_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*):?[-=](.*)\}$")


def _default_clause_literal(token: str) -> str | None:
    """The literal DEFAULT-VALUE text of TOKEN, when TOKEN is EXACTLY one
    bash `${NAME:-default}`/`${NAME-default}`/`${NAME:=default}`/
    `${NAME=default}` construct -- None otherwise. Bash evaluates this
    construct to DEFAULT whenever NAME is unset (or, for the
    `:`-prefixed forms, empty): a zero-assignment mechanism for embedding
    literal text directly in a token -- `${NEVER_SET:-uv}
    ${NEVER_SET2:-install} foo` needs no `NAME=` assignment anywhere in
    the command at all to resolve, at real bash's own runtime, to a real
    `uv install foo`. Found live by Step 8 independent review, ninth
    round (issue #1326), against the sibling module's own B1a/B1b rules
    this file's own copies below are adapted from -- neither ever looked
    at a token's own embedded default-clause text, so this fully
    bypassed even the most basic install-verb detection."""
    match = _DEFAULT_CLAUSE_RE.match(token)
    return match.group(2) if match else None


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


def _assigned_literals(tokens: list[str]) -> dict[str, str]:
    """Map each NAME=value assignment token's variable name to its
    (lowercased) RHS value. Keyed by variable name (not a flat set of
    values) so a caller can confirm a dynamic token *actually references*
    the specific variable supplying a value, rather than merely testing
    whether some assignment anywhere in the whole command happens to
    supply a matching value -- see
    _rule_b1b_dynamic_word_assigned_tool_and_verb's own docstring for the
    false positive this closes (found live by Step 8 independent review,
    issue #1326)."""
    values: dict[str, str] = {}
    for token in tokens:
        if _is_dynamic(token):
            continue
        match = _ASSIGN_RE.match(token)
        if match:
            values[match.group(1)] = match.group(2).lower()
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


def _rule_gh_any(segments: list[list[str]], name_to_value: dict[str, str]) -> str | None:
    """`gh` itself hidden behind a variable (`G=gh; $G pr merge 1`) needs
    its own indirection check, distinct from `_rule_b1a`/`_rule_b1b`
    above: `_WATCHED_TOOLS` in this file never includes "gh" at all (it
    is denied entirely, any subcommand, via this dedicated blanket rule
    instead of the adjacent-verb table those B-rules serve), so neither
    generic rule ever considers `gh` a watched tool. Found live by Step 8
    independent review, fourth round (issue #1326). Only `seg[0]` (the
    command word) is checked -- `gh` referenced anywhere else in the
    segment is not this rule's concern -- and no verb pairing is needed,
    since every `gh` subcommand is denied regardless of which one it is.

    `seg[0]`'s own embedded `${NEVER_SET:-gh}`-shaped default-clause text
    (via `_default_clause_literal`) counts as a "value" here too,
    alongside a referenced variable's own assigned value -- found live by
    Step 8 independent review, ninth round (issue #1326): see
    `_default_clause_literal`'s own docstring."""
    for seg in segments:
        if not seg:
            continue
        if not _is_dynamic(seg[0]) and seg[0].lower() == "gh":
            return "the gh CLI, not permitted inside a task-level agent (read or write)"
        if _is_dynamic(seg[0]):
            referenced = set(_VAR_REF_RE.findall(seg[0]))
            values = {name_to_value[name] for name in referenced if name in name_to_value}
            default_text = _default_clause_literal(seg[0])
            if default_text is not None:
                values.add(default_text.lower())
            if "gh" in values:
                return "the gh CLI, not permitted inside a task-level agent (read or write)"
    return None


# git's own value-taking global options that can appear as a SEPARATE
# following token (not just fused with "="): the two short options -c/-C
# (both collapse to lowered "-c") plus every long option from git's own
# usage synopsis that takes a value. `--exec-path`/`--html-path`/
# `--man-path`/`--info-path` are deliberately excluded: confirmed against
# git's own usage synopsis, `--exec-path` takes an OPTIONAL value only in
# the fused `--exec-path=<path>` form, and the other three take no value
# at all -- none of the three ever separates a `push` token from `git`
# the way a genuine separate-token value would.
_GIT_LONG_VALUE_FLAGS = {"--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}


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
            # -c/-C and git's own value-taking LONG global options
            # (--git-dir, --work-tree, --namespace, --super-prefix,
            # --config-env) all accept the value as a separate following
            # token, not only fused with "=" (`--git-dir=<path>`). Skip
            # that value token too, or `git --git-dir /tmp/repo push`
            # would stop scanning at the non-flag-shaped path argument
            # and miss the `push` after it -- the long-option
            # separate-token form was found live by Step 8 independent
            # review, fourth round (issue #1326): only the fused `=` form
            # was ever tested, so `git --git-dir /tmp/repo push origin
            # master` -- confirmed to actually push with real git --
            # went undetected by this task-agent hard-deny rule. Every
            # OTHER 2-char short global option (-v, -h, -p, -P) is
            # boolean and takes no argument, confirmed against git's own
            # usage synopsis -- found live by Step 8, second round.
            if (flag == "-c" or flag in _GIT_LONG_VALUE_FLAGS) and j < len(literals):
                next_tok = literals[j]
                if next_tok is not None and not next_tok.startswith("-"):
                    j += 1
        if j < len(literals) and literals[j] == "push":
            return True
    return any("git push" in lit for lit in (t.lower() for t in seg if not _is_dynamic(t)))


def _rule_git_push(segments: list[list[str]], name_to_value: dict[str, str]) -> str | None:
    for seg in segments:
        if _is_git_push_segment(seg):
            return "git push, not permitted inside a task-level agent (worktree merge-back is main-thread-only)"
        if not seg:
            continue
        if _is_dynamic(seg[0]):
            # A dynamic command word with a literal "push" token already
            # present elsewhere in the SAME segment (`$G push origin
            # main`) needs no indirection lookup at all -- "push" is
            # right there. Found live by Step 8 independent review, third
            # round (issue #1326): the indirection-only check below never
            # fires here, since "push" is a plain literal argument, not
            # referenced by any dynamic token, so it never entered
            # `values`. Mirrors what the sibling
            # hooks/gitapex_check_bash_safety.py module already does for
            # git-push detection via its own
            # _rule_b1a_dynamic_word_same_segment_verb call.
            if any((not _is_dynamic(t)) and t.lower() == "push" for t in seg[1:]):
                return "git push, not permitted inside a task-level agent (worktree merge-back is main-thread-only)"
            # Scoped to the variable names THIS segment's own dynamic
            # tokens actually reference -- not "some assignment anywhere
            # in the whole command happens to be named git/push,"
            # regardless of whether this segment references it at all
            # (found live by Step 8 independent review, issue #1326: the
            # earlier flat-set version denied
            # `GIT=x; PUSH=y; echo done; Z=$(mktemp); "$Z" --help`).
            #
            # A tool or verb embedded directly as a
            # `${NEVER_SET:-git}`-shaped token's own DEFAULT text (via
            # _default_clause_literal) counts as a "value" here too,
            # alongside a referenced variable's own assigned value --
            # found live by Step 8 independent review, ninth round (issue
            # #1326): see _default_clause_literal's own docstring.
            referenced: set[str] = set()
            values: set[str] = set()
            for tok in seg:
                if not _is_dynamic(tok):
                    continue
                referenced |= set(_VAR_REF_RE.findall(tok))
                default_text = _default_clause_literal(tok)
                if default_text is not None:
                    values.add(default_text.lower())
            values |= {name_to_value[name] for name in referenced if name in name_to_value}
            if "git" in values and "push" in values:
                return "git push, not permitted inside a task-level agent (worktree merge-back is main-thread-only)"
        if len(seg) > 1 and not _is_dynamic(seg[0]) and seg[0].lower() == "git" and _is_dynamic(seg[1]):
            return "git push, not permitted inside a task-level agent (worktree merge-back is main-thread-only)"
    return None


def _rule_b1a_dynamic_word_same_segment_verb(seg: list[str], verb_set: set[str]) -> bool:
    """A verb hidden in a `${NEVER_SET:-install}`-shaped token's own
    DEFAULT text counts too (via `_default_clause_literal`), not just a
    plain literal token -- found live by Step 8 independent review, ninth
    round (issue #1326): see `_default_clause_literal`'s own docstring."""
    if not seg or not _is_dynamic(seg[0]):
        return False
    literals = {t.lower() for t in seg[1:] if not _is_dynamic(t)}
    for tok in seg[1:]:
        default_text = _default_clause_literal(tok)
        if default_text is not None:
            literals.add(default_text.lower())
    return bool(literals & verb_set)


def _rule_b1b_dynamic_word_assigned_tool_and_verb(
    seg: list[str], name_to_value: dict[str, str], verb_set: set[str]
) -> bool:
    """Scoped to the variable names THIS segment's own dynamic tokens
    actually reference -- not "some assignment anywhere in the whole
    command happens to look like a tool and some unrelated assignment
    happens to look like a verb," which is unsound: found live by Step 8
    independent review (issue #1326), `TOOL=uv; VERB=install; echo done;
    X=$(mktemp); "$X" --help` was wrongly denied even though `$X`
    references neither TOOL nor VERB. `seg[0]` (the command word) must
    itself be dynamic, or a dynamic argument to an otherwise-literal,
    harmless command would be denied for constructing no dynamic command
    at all.

    A tool or verb embedded directly as a `${NEVER_SET:-uv}`-shaped
    token's own DEFAULT text (via `_default_clause_literal`) counts as a
    "value" here too, alongside a referenced variable's own assigned
    value -- found live by Step 8 independent review, ninth round (issue
    #1326): see `_default_clause_literal`'s own docstring."""
    if not seg or not _is_dynamic(seg[0]):
        return False
    referenced: set[str] = set()
    values: set[str] = set()
    for tok in seg:
        if not _is_dynamic(tok):
            continue
        referenced |= set(_VAR_REF_RE.findall(tok))
        default_text = _default_clause_literal(tok)
        if default_text is not None:
            values.add(default_text.lower())
    if not referenced and not values:
        return False
    values |= {name_to_value[name] for name in referenced if name in name_to_value}
    return bool(values & _WATCHED_TOOLS) and bool(values & verb_set)


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

    gh_hit = _rule_gh_any(segments, assigned)
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

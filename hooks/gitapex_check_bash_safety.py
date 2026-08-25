"""Token-based classifier backing hooks/check-bash-safety.sh (issue #1326,
Stage 1 of the root-cause analysis on #1326).

Why this exists: the predecessor implementation matched a bash extended
regex against the raw, unexpanded shell source text of tool_input.command.
That is a substring scan over source text, not a check against what bash
will actually execute -- and bash's own expansion (quote removal,
parameter/array expansion, command substitution) makes the two different
strings. Live-verified (issue #1326): variable-split tool+verb
(`A=uv; B=install; $A $B foo`), quote-splitting (`u""v install foo`),
`${IFS}` substitution, positional-parameter indirection, and several other
techniques all defeated the raw-substring gate while still resolving to
the exact denied invocation once bash actually ran them -- and the
identical technique defeated `pip install`, `gh pr merge`, and `git push`
just as easily; this is a property of the whole regex-substring design,
not one pattern.

Root-cause analysis (dispatched to an independent subagent, recorded on
#1326) rejected a `bash -x` sandboxed-trace-normalization redesign on two
independently reproduced grounds: it is not side-effect-free (an empty-PATH
sandbox still let `/bin/rm` run by absolute path and let plain redirections
truncate files -- executing the exact untrusted input this gate exists to
police), and an environment-divergence oracle (`command -v uv && uv install
foo`) defeats it regardless of isolation strength, because the sandbox's
own absence of the real tool is directly observable and branch-able by the
attacker-controlled command. Widening isolation only widens that gap.

That analysis also measured that no text-only gate can be both sound and
low-false-positive: a policy that soundly denies every non-literal
(dynamic) command produced a 28% false-positive rate against ordinary,
legitimate dynamic bash usage. This module is therefore Stage 1 of a
two-stage plan, not a claimed full closure:

  1. Tokenize with the standard library's own shlex (POSIX quote/backslash
     rules, punctuation-aware so shell operators become their own tokens)
     instead of matching raw text. Dequoting alone soundly closes the
     quote-splitting and backslash-escape bypass subclass with no new gap
     (`u""v install` and `gi""t push` both dequote to their plain form).
  2. Deterministically normalize the well-known `${IFS}`/`$IFS`
     whitespace-substitution trick by splitting on that exact marker before
     matching -- sound, not heuristic, because that marker means
     "whitespace" in exactly the exploited construction.
  3. For the small number of remaining bypass techniques that hide a
     tool/verb pair behind genuine shell indirection (a variable, a
     positional parameter, an array, a command substitution used as the
     command word or a verb-position argument), apply a narrow, adversarially
     re-tested heuristic (see _rule_b1a_dynamic_word_same_segment_verb,
     _rule_b1b_dynamic_word_assigned_tool_and_verb, and
     _rule_b2_watched_tool_dynamic_verb_position below) that denies only
     when a *specific*, checked structural pattern is present -- not merely
     "this command contains a dynamic construct anywhere" (that blanket
     form is exactly what produced the 28% false-positive rate).

Known, disclosed limitation (per dimension 9 of
skills/evaluating-deterministic-gate-quality/references/dimensions.md):
this does NOT close every conceivable indirection. Verb reconstruction
that never places the tool or verb name as its own literal token anywhere
in the command -- string-slicing a fused variable
(`cmd=uvinstall; eval "${cmd:0:2} ${cmd:2}" foo`) or building the argv
through an array literal assignment
(`A=(uv); V=(install); "${A[@]}" "${V[@]}" foo`) -- still evades Stage 1.
Full closure requires Stage 2 (execution-boundary enforcement: a native
git pre-push hook, package-registry network-egress blocking, and gh
token re-scoping), tracked separately per #1326's own stated scope
boundary, not attempted here.

Deliberately stdlib-only (shlex, re, json) -- no new third-party
dependency, matching this repository's declarative module-management
convention and python3's already-accepted-hook-dependency status (see
hooks/gitapex_check_post_write_provenance.py and five further sibling
hooks that already shell out to python3).
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from typing import NamedTuple

# --- Tokenization ------------------------------------------------------

# shlex's own default punctuation set under punctuation_chars=True.
_SINGLE_OPS = {";", "|", "&", "(", ")", "\n"}
_MULTI_OPS = {"&&", "||"}
_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# Matches the variable name inside `$NAME`/`${NAME`/`${NAME:-default}`-style
# references -- used to confirm a dynamic token actually references a
# specific assigned variable, rather than merely testing whether some
# unrelated assignment anywhere in the whole command happens to look like a
# tool/verb (see _rule_b1b_dynamic_word_assigned_tool_and_verb's docstring).
_VAR_REF_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")


class TokenizeError(Exception):
    pass


def _is_dynamic(token: str) -> bool:
    return "$" in token or "`" in token


def _ifs_split(token: str) -> list[str]:
    """`${IFS}`/`$IFS`, unexpanded, deterministically means "whitespace" in
    the exploited construction (default IFS is space/tab/newline) -- this
    is a sound normalization, not a heuristic, unlike the dynamic-token
    rules below."""
    for marker in ("${IFS}", "$IFS"):
        if marker in token:
            parts = [p for p in token.split(marker) if p]
            if len(parts) > 1:
                return parts
    return [token]


def _split_punct_run(token: str) -> list[str]:
    """shlex's punctuation_chars mode merges adjacent punctuation
    characters into one token when nothing separates them (e.g. `);`
    becomes one token `');'`, not `)` then `;`) -- true 2-char shell
    operators (&&, ||) are the one case that must stay merged."""
    if token in _MULTI_OPS:
        return [token]
    if token and all(c in _SINGLE_OPS for c in token):
        return list(token)
    return [token]


def tokenize(command: str) -> list[str]:
    """Raises TokenizeError on anything shlex cannot parse (e.g. an
    unbalanced quote) -- the caller must fail closed on that, the same
    fail-closed discipline this hook's malformed-JSON guards already
    apply one layer up."""
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
    """Split the flat token stream into simple-command segments at shell
    control-operator boundaries (; | & && || ( ) newline)."""
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _SINGLE_OPS or token in _MULTI_OPS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [seg for seg in segments if seg]


def _assigned_literals(tokens: list[str]) -> dict[str, str]:
    """Map each NAME=value assignment token's variable name to its
    (lowercased) RHS value -- deliberately NOT every literal token in the
    command. An ordinary command argument (e.g. `add` in `git add
    file.txt`) must never count here, or an unrelated dynamic segment
    elsewhere in the same command (`git add f1 f2; result=$(date)`) would
    false-positive against it -- found live during this module's own
    adversarial self-test and fixed by this scoping.

    Keyed by variable name (not a flat set of values) so a caller can
    confirm a dynamic token *actually references* the specific variable
    supplying a value, rather than merely testing whether some assignment
    anywhere in the whole command happens to supply a matching value --
    see _rule_b1b_dynamic_word_assigned_tool_and_verb's own docstring for
    the false positive this closes (found live by Step 8 independent
    review, issue #1326)."""
    values: dict[str, str] = {}
    for token in tokens:
        if _is_dynamic(token):
            continue
        match = _ASSIGN_RE.match(token)
        if match:
            values[match.group(1)] = match.group(2).lower()
    return values


# --- Denylists -----------------------------------------------------------
# uv add/remove are deliberately absent (PR #1323 / issue #1320): they
# mutate pyproject.toml/uv.lock, a declarative, PR-diff-visible change,
# unlike uv pip install/bare uv install.

_DENIED_ADJACENT: list[tuple[str, ...]] = [
    ("pip", "install"),
    ("pip3", "install"),
    ("npm", "install"),
    ("npm", "i"),
    ("yarn", "add"),
    ("pnpm", "add"),
    ("go", "install"),
    ("brew", "install"),
    ("apt", "install"),
    ("apt-get", "install"),
    ("gem", "install"),
    ("cargo", "install"),
    ("uv", "pip", "install"),
    ("uv", "install"),
    ("plugin", "install"),
    ("gh", "issue", "create"),
    ("gh", "issue", "edit"),
    ("gh", "issue", "close"),
    ("gh", "issue", "comment"),
    ("gh", "issue", "delete"),
    ("gh", "issue", "reopen"),
    ("gh", "issue", "transfer"),
    ("gh", "issue", "pin"),
    ("gh", "issue", "unpin"),
    ("gh", "issue", "lock"),
    ("gh", "issue", "unlock"),
    ("gh", "issue", "develop"),
    ("gh", "pr", "create"),
    ("gh", "pr", "edit"),
    ("gh", "pr", "close"),
    ("gh", "pr", "comment"),
    ("gh", "pr", "merge"),
    ("gh", "pr", "review"),
    ("gh", "pr", "ready"),
    ("gh", "pr", "reopen"),
    ("gh", "pr", "lock"),
    ("gh", "pr", "unlock"),
    ("gh", "pr", "update-branch"),
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
    "gh",
    "git",
    "plugin",
}
# Leaf verbs/subcommands denied for at least one tool above -- used only as
# the dynamic-indirection suspicion signal for the B-rules below, never as
# a standalone deny list on its own (a literal command is only denied by
# _DENIED_ADJACENT/_DENIED_PHRASES or the gh-api/git-push checks).
_WATCHED_VERBS = {
    "install",
    "i",
    "add",
    "merge",
    "create",
    "edit",
    "close",
    "comment",
    "delete",
    "reopen",
    "transfer",
    "pin",
    "unpin",
    "lock",
    "unlock",
    "develop",
    "review",
    "ready",
    "update-branch",
}
_GIT_PUSH_VERB = "push"

_WRITE_METHODS = {"post", "put", "patch", "delete"}


class Verdict(NamedTuple):
    deny: bool
    reason: str
    is_git_push: bool


def _rule_a_literal(segments: list[list[str]]) -> str | None:
    """Sound: matches only against the dequoted literal-token stream, so
    quote-splitting and backslash-escaping (already resolved by shlex) and
    ${IFS} substitution (already resolved by _ifs_split) are closed for
    free, plus a same-token literal-phrase fallback for the case where an
    entire denied phrase survives inside one quoted argument (e.g.
    `echo "uv install foo" | bash`, `$(echo "uv install foo")`)."""
    for seg in segments:
        literals = [t.lower() for t in seg if not _is_dynamic(t)]
        for pattern in _DENIED_ADJACENT:
            n = len(pattern)
            for i in range(len(literals) - n + 1):
                if tuple(literals[i : i + n]) == pattern:
                    return f"a Bash command matching a denied verb sequence ({'+'.join(pattern)})"
        for literal in literals:
            for phrase in _DENIED_PHRASES:
                if phrase in literal:
                    return f"a Bash argument containing the denied phrase '{phrase}'"
    return None


def _rule_gh_api_write(segments: list[list[str]], lowered_command: str, name_to_value: dict[str, str]) -> str | None:
    """`literals` is already lowercased, matching the predecessor script's
    own case-insensitive match against its whole lowered command -- so
    `-F`/`-f` are indistinguishable here exactly as they were there.

    A `-X`/`--method` flag whose VALUE token is itself dynamically
    constructed (e.g. `-X $M`) is checked separately, against
    `name_to_value`: `literals` above has already filtered every dynamic
    token out, so the loop below can never see that a value token was
    even present, let alone what it resolves to -- found live by Step 8
    independent review (issue #1326): `M=POST; gh api .../merge -X $M`
    resolved to a real write and was wrongly allowed."""
    for seg in segments:
        literals = [t.lower() for t in seg if not _is_dynamic(t)]
        has_gh_api = any(literals[i : i + 2] == ["gh", "api"] for i in range(len(literals) - 1))
        if not has_gh_api:
            continue
        has_graphql = any(literals[i : i + 3] == ["gh", "api", "graphql"] for i in range(len(literals) - 2))
        if has_graphql and "mutation" in lowered_command:
            return "a 'gh api graphql' call containing a 'mutation' keyword"

        for i, tok in enumerate(literals):
            if tok in ("-x", "--method") and i + 1 < len(literals):
                value = literals[i + 1].lstrip("=")
                if any(value.startswith(m) for m in _WRITE_METHODS):
                    return "a 'gh api' write call (-X/--method POST/PUT/PATCH/DELETE)"
            if tok.startswith("-x") and len(tok) > 2 and any(tok[2:].startswith(m) for m in _WRITE_METHODS):
                return "a 'gh api' write call (-X/--method POST/PUT/PATCH/DELETE)"
            if tok.startswith("--method=") and any(tok[len("--method=") :].startswith(m) for m in _WRITE_METHODS):
                return "a 'gh api' write call (-X/--method POST/PUT/PATCH/DELETE)"

        for i, raw_tok in enumerate(seg):
            if _is_dynamic(raw_tok) or raw_tok.lower() not in ("-x", "--method"):
                continue
            if i + 1 >= len(seg) or not _is_dynamic(seg[i + 1]):
                continue
            referenced = set(_VAR_REF_RE.findall(seg[i + 1]))
            values = {name_to_value[name] for name in referenced if name in name_to_value}
            if values & _WRITE_METHODS:
                return "a 'gh api' write call with a dynamically constructed -X/--method value assigned from a denied write method"

        if not has_graphql:
            for tok in literals:
                if tok in ("-f", "--field", "--raw-field"):
                    return "a 'gh api' call with a field flag (-f/-F/--field/--raw-field)"
                if tok.startswith("-f") and len(tok) > 2:
                    return "a 'gh api' call with a field flag (-f/-F/--field/--raw-field)"
                if tok.startswith("--field=") or tok.startswith("--raw-field="):
                    return "a 'gh api' call with a field flag (-f/-F/--field/--raw-field)"
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
            # `-c <name>=<value>` and `-C <path>` are git's only two
            # value-taking short global options -- both collapse to the
            # same lowered "-c" token here -- and take their value as a
            # separate following token; a long option (`--git-dir=<path>`)
            # attaches its value with `=` instead. Skip that value token
            # too, or `git -C /tmp/repo push` would stop scanning at the
            # non-flag-shaped path argument and miss the `push` after it.
            # Every OTHER short global option (-v, -h, -p, -P) is boolean
            # and takes no argument, confirmed against git's own usage
            # synopsis -- originally this treated ANY 2-char flag as
            # value-taking, which wrongly swallowed the "push" token
            # itself as a boolean flag's "value" (`git -p push origin
            # main` was never detected as git push) -- found live by
            # Step 8 independent review, issue #1326.
            if flag == "-c" and j < len(literals):
                next_tok = literals[j]
                if next_tok is not None and not next_tok.startswith("-"):
                    j += 1
        if j < len(literals) and literals[j] == "push":
            return True
    return any("git push" in lit for lit in (t.lower() for t in seg if not _is_dynamic(t)))


def _rule_b1a_dynamic_word_same_segment_verb(seg: list[str], verb_set: set[str]) -> bool:
    """A segment whose command word is dynamic, with a literal watched-verb
    token present anywhere else in that SAME segment (e.g.
    `$T install foo` -- `install` sits right there). Scoped to one segment
    on purpose, so it cannot combine with an unrelated verb-shaped word in
    a different, unrelated segment."""
    if not seg or not _is_dynamic(seg[0]):
        return False
    literals = {t.lower() for t in seg[1:] if not _is_dynamic(t)}
    return bool(literals & verb_set)


def _rule_b1b_dynamic_word_assigned_tool_and_verb(
    seg: list[str], name_to_value: dict[str, str], verb_set: set[str]
) -> bool:
    """A segment with at least one dynamic token, where a variable
    actually REFERENCED by one of this segment's own dynamic tokens (not
    plain arguments -- see _assigned_literals) was assigned a watched tool
    name, and a variable referenced by one of this segment's own dynamic
    tokens was assigned a watched verb name (e.g. `A=uv; B=install; $A $B
    foo` -- both `$A` and `$B` are dynamic tokens in the SAME segment,
    referencing A and B respectively).

    Scoped to the variable names THIS segment's own dynamic tokens
    actually reference -- not "some assignment anywhere in the whole
    command happens to look like a tool and some unrelated assignment
    happens to look like a verb," which is unsound: found live by Step 8
    independent review (issue #1326), `TOOL=uv; VERB=install; echo done;
    X=$(mktemp); "$X" --help` was wrongly denied even though `$X`
    references neither TOOL nor VERB.

    `seg[0]` (the command word) must itself be dynamic -- unchanged from
    before this fix -- or a dynamic argument to an otherwise-literal,
    harmless command (e.g. `echo $A $B` where A=uv, B=install just prints
    text, it does not invoke anything) would be denied for constructing
    no dynamic command at all."""
    if not seg or not _is_dynamic(seg[0]):
        return False
    referenced: set[str] = set()
    for tok in seg:
        if _is_dynamic(tok):
            referenced |= set(_VAR_REF_RE.findall(tok))
    if not referenced:
        return False
    values = {name_to_value[name] for name in referenced if name in name_to_value}
    return bool(values & _WATCHED_TOOLS) and bool(values & verb_set)


def _rule_b2_watched_tool_dynamic_verb_position(seg: list[str]) -> bool:
    """A literal watched-tool command word whose very next argument (the
    position a subcommand/verb normally occupies) is dynamically
    constructed (e.g. `uv $x foo`, `set -- install foo; uv "$@"`).

    `git` is deliberately excluded here: it has many safe subcommands
    (status, commit, log, diff, add, ...) and the one this gate cares
    about (push) is warn-not-deny, handled by the dedicated git-push
    detection below -- folding git into this generic hard-deny rule would
    deny `git $SUBCMD ...` regardless of which subcommand actually
    resolves, a false-positive class this gate does not need to take on
    since push already has its own, narrower path."""
    if len(seg) < 2:
        return False
    first = seg[0]
    if _is_dynamic(first) or first.lower() not in (_WATCHED_TOOLS - {"git"}):
        return False
    return _is_dynamic(seg[1])


def classify(command: str) -> Verdict:
    """Classify one Bash tool_input.command string. Fails closed (deny) on
    anything shlex cannot tokenize -- an unparseable command is exactly the
    "cannot confidently classify" case dimension 15 requires denying, not
    silently allowing."""
    try:
        tokens = tokenize(command)
    except TokenizeError as error:
        return Verdict(True, f"the command could not be parsed as shell syntax ({error}). Failing closed", False)

    segments = segment_tokens(tokens)
    assigned = _assigned_literals(tokens)
    lowered_command = command.lower()

    is_git_push = any(_is_git_push_segment(seg) for seg in segments)

    literal_hit = _rule_a_literal(segments)
    if literal_hit:
        return Verdict(True, literal_hit, is_git_push)

    gh_api_hit = _rule_gh_api_write(segments, lowered_command, assigned)
    if gh_api_hit:
        return Verdict(True, gh_api_hit, is_git_push)

    for seg in segments:
        if _rule_b1a_dynamic_word_same_segment_verb(seg, _WATCHED_VERBS):
            return Verdict(
                True,
                "a Bash command word is dynamically constructed, alongside a denied verb literally "
                "present in the same command -- rewrite as a plain literal command so it can be checked",
                is_git_push,
            )
        if _rule_b1b_dynamic_word_assigned_tool_and_verb(seg, assigned, _WATCHED_VERBS):
            return Verdict(
                True,
                "a Bash command word is dynamically constructed from variables whose assigned values "
                "include both a denied tool and a denied verb -- rewrite as a plain literal command",
                is_git_push,
            )
        if _rule_b2_watched_tool_dynamic_verb_position(seg):
            return Verdict(
                True,
                "a watched tool is invoked with a dynamically constructed subcommand/verb argument -- "
                "rewrite as a plain literal command so it can be checked",
                is_git_push,
            )
        obfuscated_git_push_second_token = (
            seg and not _is_dynamic(seg[0]) and seg[0].lower() == "git" and len(seg) > 1 and _is_dynamic(seg[1])
        )
        if (
            _rule_b1a_dynamic_word_same_segment_verb(seg, {_GIT_PUSH_VERB})
            or _rule_b1b_dynamic_word_assigned_tool_and_verb(seg, assigned, {_GIT_PUSH_VERB})
            or obfuscated_git_push_second_token
        ):
            is_git_push = True

    return Verdict(False, "no denied pattern matched", is_git_push)


# --- stdin JSON entrypoint ------------------------------------------------


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
    print(
        json.dumps(
            {
                "decision": "deny" if verdict.deny else "allow",
                "reason": verdict.reason,
                "is_git_push": verdict.is_git_push,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

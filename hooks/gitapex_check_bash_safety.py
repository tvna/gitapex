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

A second, distinct instance of the same underlying class (found live by
Step 8 independent review, fourth round): `_rule_gh_api_write`'s own
`gh api graphql` "mutation" keyword check is a raw substring scan over
the whole command text, not a token match -- sound against a literal
"mutation" keyword, but not against one reconstructed at runtime by
concatenating two or more separately-assigned variables
(`A=muta; B=tion; Q="${A}${B} { ... }"; gh api graphql -f query="$Q"`).
Soundly closing this would require resolving nested `${NAME}` references
through recursive variable substitution -- the same unbounded-
reconstruction problem as the verb-reconstruction residual above,
manifesting here for a keyword embedded in a free-text query value
instead of a command/verb token. Deliberately not attempted in Stage 1;
pinned as `graphql-mutation-keyword-variable-concatenation` in
hooks/test_gitapex_check_bash_safety.py's own `KNOWN_BYPASS_COMMANDS`.

Closed by fifth-round Step 8 independent review: `_gh_api_method_dynamic_
value`/`_gh_api_field_dynamic_hit` (and the earlier literal-token scans)
only ever recognized a dynamic VALUE fused onto a literal `-X`/`--method`/
`-f`/`--field`/`--raw-field` flag prefix -- none of them handled the flag
NAME ITSELF being a bare variable reference as its own token
(`F=-X; M=POST; gh api .../merge $F $M`), since a token that is purely
`$F` carries no literal flag-shaped text at all for those scans to match
against. Unlike the graphql residual above, this one IS closed in Stage
1: `_resolve_bare_var` narrowly resolves a token only when it is *exactly*
one bare `$NAME`/`${NAME}` reference (no other shape), then
`_gh_api_method_flagname_dynamic_hit`/`_gh_api_field_flagname_dynamic_hit`
check whether that resolves to a known flag name -- the same bounded,
single-level `name_to_value` lookup every other B-rule here already uses,
not the unbounded recursive reconstruction the two residuals above would
require.

Closed by sixth-round Step 8 independent review: both `_gh_api_method_
dynamic_hit` and `_gh_api_method_flagname_dynamic_hit` resolved a dynamic
`-X`/`--method` VALUE by collecting every variable the value token
referenced and checking whether any ONE of their individually-resolved
values was itself a complete write method -- so a value split across
multiple concatenated variables (`-X "$M1$M2"` with `M1=PO`, `M2=ST`)
was never recognized, even though bash concatenates them into a real
`POST` write with no separator. Closed via `_substitute_var_refs`, which
replaces every `$NAME`/`${NAME}` reference in a token with its resolved
value (preserving surrounding literal text) and checks the *reconstructed*
string -- still a single, bounded substitution pass over `name_to_value`
entries that are themselves already plain literal strings, not the
unbounded recursive reconstruction the graphql-mutation-keyword residual
above requires (that residual concatenates variables into a keyword
buried in free-text search content; this one concatenates variables into
a flag's own value, a small bounded comparison set of four write
methods).

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
# Matches a token that is PURELY a single variable reference with nothing
# else fused onto it (`$F`, `${F}`) -- deliberately excludes every other
# dynamic shape (`${F}x`, `$F$G`, `` `cmd` ``) so resolving it stays the
# same narrow, adversarially-tested heuristic class as the other B-rules:
# denies only a specific, checked structural pattern, never "this token is
# dynamic somehow." See _resolve_bare_var below.
_BARE_VAR_RE = re.compile(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?$")


def _resolve_bare_var(token: str, name_to_value: dict[str, str]) -> str | None:
    """Resolve TOKEN to its assigned (already-lowercased) value only when
    TOKEN is a bare single variable reference -- None otherwise, including
    when the reference exists but the variable was never assigned a
    literal value (e.g. assigned from a command substitution)."""
    match = _BARE_VAR_RE.match(token)
    if not match:
        return None
    return name_to_value.get(match.group(1))


# Matches one `$NAME`/`${NAME}` reference anywhere in a token, capturing
# its full span (including the braces, when present) so _substitute_var_refs
# below can replace exactly that span -- unlike _VAR_REF_RE, which only
# captures the name and is used solely to collect referenced names, never
# to reconstruct token text.
_VAR_REF_FULL_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _substitute_var_refs(token: str, name_to_value: dict[str, str]) -> str | None:
    """Reconstruct TOKEN with every `$NAME`/`${NAME}` reference replaced by
    its assigned (already-lowercased) value, preserving any literal text
    around or between references -- e.g. `$M1$M2` with M1="po", M2="st"
    becomes "post". Returns None (cannot soundly resolve) if any
    referenced variable was never assigned a literal value.

    Bounded and sound, not the unbounded recursive reconstruction the
    module docstring's graphql-mutation-keyword residual disclaims:
    `name_to_value`'s own entries are themselves already plain literal
    strings (a dynamic RHS is filtered out before ever entering
    `name_to_value` -- see `_assigned_literals`), so this is exactly one
    substitution pass over TOKEN, never a re-expansion of a substituted
    value that might itself contain `$`. A reference to an unassigned
    variable, or non-`$NAME` content such as a backtick command
    substitution, is left as literal text in the result rather than
    resolved -- it simply will not match a known value afterward, the
    same fail-closed-to-"no match" posture `_resolve_bare_var` already
    takes for an unassigned bare reference."""
    pieces: list[str] = []
    pos = 0
    for match in _VAR_REF_FULL_RE.finditer(token):
        name = match.group(1) or match.group(2)
        if name not in name_to_value:
            return None
        pieces.append(token[pos : match.start()])
        pieces.append(name_to_value[name])
        pos = match.end()
    pieces.append(token[pos:])
    return "".join(pieces)


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
    # "api" is not a denied-adjacent verb on its own (a plain `gh api
    # <read-path>` is legitimate) -- it is included here only so the B1a/
    # B1b indirection rules recognize `gh`+`api` as a suspicious pairing
    # when BOTH are hidden behind variables (`G=gh; A=api; $G $A ... -X
    # POST`), the same way they already recognize `gh`+`merge` for
    # `gh pr merge` indirection. Found live by Step 8 independent review,
    # fourth round (issue #1326): a literal `gh` with a dynamic
    # subcommand was already caught by Rule B2, but BOTH tool and
    # subcommand dynamic evaded every existing rule, since `_rule_gh_api_
    # write`'s own write-detection logic (the -X/-f flag checks) is not
    # wired into the B-rule indirection machinery at all. Once indirection
    # is detected this way the whole `gh api` invocation is denied
    # outright, without inspecting whether it would have been a read or a
    # write once resolved -- the same "cannot confidently classify a
    # resolved-only-at-runtime command, so deny" posture the other B-rules
    # already take.
    "api",
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


_METHOD_FLAG_HIT = "a 'gh api' write call (-X/--method POST/PUT/PATCH/DELETE)"
_METHOD_FLAG_DYNAMIC_HIT = (
    "a 'gh api' write call with a dynamically constructed -X/--method value assigned from a denied write method"
)
_FIELD_FLAG_HIT = "a 'gh api' call with a field flag (-f/-F/--field/--raw-field)"


def _gh_api_method_literal_hit(literals: list[str]) -> bool:
    """Literal `-X`/`--method` flag, as a separate token, fused with `=`,
    or fused directly, whose value is itself a literal write method."""
    for i, tok in enumerate(literals):
        if tok in ("-x", "--method") and i + 1 < len(literals):
            value = literals[i + 1].lstrip("=")
            if any(value.startswith(m) for m in _WRITE_METHODS):
                return True
        if tok.startswith("-x") and len(tok) > 2 and any(tok[2:].startswith(m) for m in _WRITE_METHODS):
            return True
        if tok.startswith("--method=") and any(tok[len("--method=") :].startswith(m) for m in _WRITE_METHODS):
            return True
    return False


def _gh_api_method_dynamic_value(seg: list[str], index: int, raw_tok: str) -> str | None:
    """The dynamically constructed value part of a `-X`/`--method` flag at
    `seg[index]`, in whichever of the three shapes it takes (separate
    token, fused with `=`, or fused directly) -- or None if `raw_tok`
    is not a `-X`/`--method` flag carrying a dynamic value at all."""
    if _is_dynamic(raw_tok):
        lowered_tok = raw_tok.lower()
        # `.lstrip("=")`: `-x=$var` and `-x$var` both slice to a value part
        # starting with the shape's own separator character (`=`) or none
        # at all -- stripping it here matches `_gh_api_method_literal_hit`'s
        # own established `.lstrip("=")` treatment for its separate-token
        # case, and keeps the value part a clean comparand for
        # `_substitute_var_refs`'s reconstructed-string check below, which
        # (unlike the old per-variable-name lookup this replaced) preserves
        # every character of surrounding literal text rather than ignoring
        # a leading "=" incidentally.
        if lowered_tok.startswith("-x") and len(raw_tok) > 2:
            return raw_tok[2:].lstrip("=")
        if lowered_tok.startswith("--method="):
            return raw_tok[len("--method=") :]
        return None
    if raw_tok.lower() in ("-x", "--method") and index + 1 < len(seg) and _is_dynamic(seg[index + 1]):
        return seg[index + 1]
    return None


def _gh_api_method_dynamic_hit(seg: list[str], name_to_value: dict[str, str]) -> bool:
    """A `-X`/`--method` flag whose VALUE is itself dynamically
    constructed -- as a separate token (`-X $M`), fused with `=` (`-X=$M`,
    `--method=$M`), or fused directly (`-X$M`, `-X"$M"` -- shlex dequotes
    the quoted form to the same single token as the unquoted one) --
    resolved via `name_to_value`. Checked separately from
    `_gh_api_method_literal_hit`: the literal-token scan there filters
    every dynamic token out first, so it can never see that a value was
    even present, let alone what it resolves to -- found live by Step 8
    independent review (issue #1326), in two rounds: the separate-token
    form first (`M=POST; gh api .../merge -X $M` resolved to a real
    write and was wrongly allowed), then the fused forms in a second
    round after the first fix landed. Resolved via `_substitute_var_refs`
    (not a per-variable value set): found live by Step 8 independent
    review, sixth round (issue #1326) -- `-X "$M1$M2"` with `M1=PO`,
    `M2=ST` resolves to a real `POST` write once bash concatenates the two
    references, but checking each referenced variable's value separately
    (the prior approach) never recognized the concatenation, since
    neither "po" nor "st" alone is a write method."""
    for i, raw_tok in enumerate(seg):
        dynamic_value_part = _gh_api_method_dynamic_value(seg, i, raw_tok)
        if dynamic_value_part is None:
            continue
        resolved = _substitute_var_refs(dynamic_value_part, name_to_value)
        if resolved is not None and any(resolved.startswith(m) for m in _WRITE_METHODS):
            return True
    return False


def _gh_api_method_flagname_dynamic_hit(seg: list[str], name_to_value: dict[str, str]) -> bool:
    """The -X/--method flag NAME ITSELF hidden behind a bare variable
    reference as its own token (`F=-X; gh api .../merge $F POST`), with
    the write-method value following as a separate token -- literal or
    itself a bare variable reference. Found live by Step 8 independent
    review, fifth round (issue #1326): every prior fix here assumed the
    flag token itself carried a literal "-x"/"--method" text prefix
    somewhere in it; a token that is PURELY a variable reference has no
    such prefix, so neither the literal-token scan
    (`_gh_api_method_literal_hit`) nor the fused-value dynamic scan
    (`_gh_api_method_dynamic_hit`) above ever recognized it as a flag at
    all -- both key off literal text inside the token, and this token has
    none. The value token is resolved via `_substitute_var_refs` (not
    `_resolve_bare_var`), so a write-method value split across multiple
    concatenated variables (`$F "$M1$M2"`) is caught too -- the same gap
    `_gh_api_method_dynamic_hit` above had, found live by Step 8
    independent review, sixth round (issue #1326), against this
    function's own flag-name-indirection case."""
    for i, raw_tok in enumerate(seg):
        if _resolve_bare_var(raw_tok, name_to_value) not in ("-x", "--method"):
            continue
        if i + 1 >= len(seg):
            continue
        value_tok = seg[i + 1]
        value = value_tok.lower() if not _is_dynamic(value_tok) else _substitute_var_refs(value_tok, name_to_value)
        if value is not None and any(value.startswith(m) for m in _WRITE_METHODS):
            return True
    return False


def _gh_api_field_literal_hit(literals: list[str]) -> bool:
    """A literal `-f`/`-F`/`--field`/`--raw-field` token, as a separate
    token or fused with a literal value -- this rule never cares about
    the field VALUE, only the flag's presence."""
    for tok in literals:
        if tok in ("-f", "--field", "--raw-field"):
            return True
        if tok.startswith("-f") and len(tok) > 2:
            return True
        if tok.startswith("--field=") or tok.startswith("--raw-field="):
            return True
    return False


def _gh_api_field_dynamic_hit(seg: list[str]) -> bool:
    """A `-f`/`--field`/`--raw-field` flag fused directly with a dynamic
    value (`-f$X`, `--field=$X`, `--raw-field=$X`) makes the WHOLE token
    dynamic, so it never reaches `_gh_api_field_literal_hit`'s
    literal-token scan at all -- found live by Step 8 independent review,
    third round (issue #1326), the same fused-token gap the -X/--method
    fix had to close separately. No `name_to_value` lookup needed here:
    unlike the method flag, this rule never inspects the field value."""
    for raw_tok in seg:
        if not _is_dynamic(raw_tok):
            continue
        lowered_tok = raw_tok.lower()
        if lowered_tok.startswith("-f") and len(raw_tok) > 2:
            return True
        if lowered_tok.startswith("--field=") or lowered_tok.startswith("--raw-field="):
            return True
    return False


def _gh_api_field_flagname_dynamic_hit(seg: list[str], name_to_value: dict[str, str]) -> bool:
    """Same class as `_gh_api_method_flagname_dynamic_hit`, for
    -f/-F/--field/--raw-field: the flag NAME itself hidden behind a bare
    variable reference (`FF=--field; gh api ... $FF name=value`). Unlike
    the method flag, this rule never inspects the field value -- presence
    of the flag alone is denied, matching `_gh_api_field_literal_hit`'s
    own scope. `-F` is not listed separately: `name_to_value`'s own
    values are already lowercased (`_assigned_literals`), so `FF=-F`
    resolves to `"-f"`, the same string `-f` itself lowercases to."""
    return any(_resolve_bare_var(raw_tok, name_to_value) in ("-f", "--field", "--raw-field") for raw_tok in seg)


def _rule_gh_api_write(segments: list[list[str]], lowered_command: str, name_to_value: dict[str, str]) -> str | None:
    """`literals` is already lowercased, matching the predecessor script's
    own case-insensitive match against its whole lowered command -- so
    `-F`/`-f` are indistinguishable here exactly as they were there.
    Orchestrates the four independent scanning passes above; kept
    deliberately thin (each pass owns its own branching) so this
    function's own cyclomatic complexity stays low."""
    for seg in segments:
        literals = [t.lower() for t in seg if not _is_dynamic(t)]
        has_gh_api = any(literals[i : i + 2] == ["gh", "api"] for i in range(len(literals) - 1))
        if not has_gh_api:
            continue
        has_graphql = any(literals[i : i + 3] == ["gh", "api", "graphql"] for i in range(len(literals) - 2))
        if has_graphql and "mutation" in lowered_command:
            return "a 'gh api graphql' call containing a 'mutation' keyword"

        if _gh_api_method_literal_hit(literals):
            return _METHOD_FLAG_HIT
        if _gh_api_method_dynamic_hit(seg, name_to_value):
            return _METHOD_FLAG_DYNAMIC_HIT
        if _gh_api_method_flagname_dynamic_hit(seg, name_to_value):
            return _METHOD_FLAG_DYNAMIC_HIT

        if not has_graphql:
            if _gh_api_field_literal_hit(literals):
                return _FIELD_FLAG_HIT
            if _gh_api_field_dynamic_hit(seg):
                return _FIELD_FLAG_HIT
            if _gh_api_field_flagname_dynamic_hit(seg, name_to_value):
                return _FIELD_FLAG_HIT
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
            # `-c <name>=<value>` and `-C <path>` are git's own value-
            # taking short global options -- both collapse to the same
            # lowered "-c" token here -- and `--git-dir <path>`,
            # `--work-tree <path>`, `--namespace <name>`,
            # `--super-prefix <path>`, `--config-env <name>=<envvar>` are
            # git's own value-taking LONG global options, all of which
            # also accept the value as a separate following token, not
            # only fused with "=" (`--git-dir=<path>`). Skip that value
            # token too, or `git -C /tmp/repo push` / `git --git-dir
            # /tmp/repo push` would stop scanning at the non-flag-shaped
            # path argument and miss the `push` after it. The long-option
            # separate-token form was found live by Step 8 independent
            # review, fourth round (issue #1326): only the fused `=` form
            # was ever tested, so `git --git-dir /tmp/repo push origin
            # master` -- confirmed to actually push with real git --
            # went undetected. Every OTHER short global option (-v, -h,
            # -p, -P) is boolean and takes no argument, confirmed against
            # git's own usage synopsis -- originally this treated ANY
            # 2-char flag as value-taking, which wrongly swallowed the
            # "push" token itself as a boolean flag's "value" (found live
            # by Step 8, second round).
            if (flag == "-c" or flag in _GIT_LONG_VALUE_FLAGS) and j < len(literals):
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

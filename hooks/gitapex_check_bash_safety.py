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

Closed by seventh-round Step 8 independent review, against the sixth
round's own fix: `_substitute_var_refs` preserves a token's literal text
exactly as typed -- only the substituted variable *values* are
already-lowercased (per `_assigned_literals`'s own convention) -- so an
uppercase literal fragment fused with a variable in the SAME token
(`-X "PO$M"` with `M=ST`) reconstructed to "POst", which the
case-sensitive `.startswith()` comparison never matched against the
lowercase `_WRITE_METHODS` set. Every round-6 test exercised only a
whole-variable-per-fragment split (`M1=PO; M2=ST`), which happens to
already be all-lowercase after resolution, so this case-normalization gap
went unexercised until this round. Closed by lowercasing the
*reconstructed* string immediately before the write-method comparison at
both call sites, matching the lowercasing convention every literal-token
comparison in this module already follows.

Closed by eighth-round Step 8 independent review, a more fundamental gap
than rounds 6-7: shlex's own quote removal (tokenize's whole reason for
existing) discards WHICH characters were originally inside quotes. A
quoted, bounded reference immediately followed by more identifier-shaped
literal text (`"$M"ST`) and a bare, unquoted reference whose name simply
happens to be longer (`$MST`) both dequote to the *identical* raw token
text -- there is no way to recover, from the token alone, which reading
bash actually used. The prior single-greedy-match version of what is now
`_substitute_var_refs_candidates` always assumed the maximal-munch
(unquoted) reading, so `M=PO; gh api .../merge -X"$M"ST` -- a real
`-XPOST` write, confirmed via `bash -c` argv expansion -- was wrongly
allowed, since "MST" itself was never assigned. Closed not by picking a
different single guess, but by trying every non-empty prefix of an
unbraced identifier run as a candidate variable name (`_unbraced_ref_
options`) and checking every resulting reading (`_write_method_candidate_
hit`) -- a real write hidden behind either interpretation is now caught.
Still bounded, not the graphql residual's unbounded recursion: the
branching factor is the length of one already-fixed identifier run, not
re-expansion of a value that might itself contain `$` -- and an explicit
cap (`_MAX_SUBSTITUTION_CANDIDATES`) fails closed (treats the token as an
unresolved-but-plausible match) rather than silently truncating if a
pathological token's combinatorial expansion would exceed it.

Closed by the same eighth-round Step 8 independent review, immediately
after the fix above: the identical quote-boundary ambiguity also applies
when the -X/--method/-f/--field flag NAME itself (not just its value) is
fused directly with its own value in the SAME token -- `F=-X; gh api
.../merge "$F"POST` dequotes to the single token `$FPOST`, and
`FF=-f; gh api ... "$FF"name=value` dequotes to `$FFname=value`. Neither
the bare-anchored flag-name check (round 5, requires the flag token to be
*exactly* `$NAME`, nothing fused after it) nor the literal-text-prefix
dynamic-value check (round 2/6/7/8, requires the token to already start
with literal "-x"/"--method"/"-f"/"--field"/"--raw-field" text) recognizes
this shape, since the flag character itself is not literally present
anywhere in the token's own text before substitution. Closed by
`_gh_api_method_fused_flagname_dynamic_hit`/`_gh_api_field_fused_
flagname_dynamic_hit`, which check every candidate reconstruction of the
WHOLE token (via `_substitute_var_refs_candidates`) against the same
fused-flag shapes already recognized for a literal token -- not a new
detection rule, only extending an existing one to a token whose resolved
reading was not knowable until substitution.

Closed by ninth-round Step 8 independent review, a DIFFERENT bypass class
than rounds 5-8 (those all shared one root cause -- shlex's own quote
removal; this one is bash's own default-value expansion): bash's
`${NAME:-default}`/`${NAME-default}`/`${NAME:=default}`/`${NAME=default}`
parameter expansion evaluates to the literal DEFAULT text whenever NAME
is unset (or, for the `:`-prefixed forms, empty) -- a zero-assignment
mechanism for embedding literal text directly in a token. Before this
fix, `_substitute_var_refs_candidates` only ever recognized `$NAME`/
`${NAME}`, so the entire `${...}` construct was left as untouched literal
text and never matched any write-method comparison
(`gh api .../merge -X${TOTALLY_NEVER_MENTIONED-POST}` -- confirmed via
real bash argv expansion to resolve to an actual `-XPOST` write -- was
wrongly allowed). More severely, the SAME construct also fully bypassed
`_rule_b1a_dynamic_word_same_segment_verb`/`_rule_b1b_dynamic_word_
assigned_tool_and_verb` -- the most basic install-verb/gh-pr-merge
detection, not just the gh-api-specific checks rounds 5-8 closed --
since neither rule ever looked at a token's own embedded default-clause
text, only a literal token's own text or a referenced variable's
assigned value: `${NEVER_SET:-uv} ${NEVER_SET2:-install} foo` (confirmed
via real bash to resolve to a genuine `uv install foo`) needed NO
variable assignment anywhere in the command at all. Closed via
`_default_clause_literal` (an anchored, whole-token extraction used by
the B-rules) and a third alternative added to `_substitute_var_refs_
candidates`'s own regex (a non-anchored form, so it can also be found
fused within a larger token, e.g. `-X${NAME-POST}`) -- both contribute
the literal DEFAULT text as a candidate reading, PLUS NAME's own resolved
value if it also happens to be assigned (an extra safety-margin
candidate, since this classifier cannot know at gate time whether NAME
will actually be unset/empty at bash's own real runtime). The DEFAULT
text itself is not recursively re-scanned for further `$` references it
might contain (e.g. `${UNSET:-$OTHER}`) -- a disclosed residual, the same
"not the unbounded reconstruction problem" boundary already drawn
elsewhere in this module. The identical fix was ported to the
self-contained duplicate at
skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py
(its own B1a/B1b, `_rule_gh_any`, and `_rule_git_push` all shared the
same gap).

Closed by tenth-round Step 8 independent review, a THIRD distinct bypass
class (rounds 5-8: shlex's own quote removal; round 9: bash's default-
value expansion; this one: bash's own `${!NAME}` indirect-reference
syntax): `${!NAME}` is a TWO-LEVEL lookup -- NAME's own assigned value
names a SECOND variable, and the whole expression evaluates to THAT
variable's own assigned value (`TOOLREF=T; T=uv; ${!TOOLREF}` resolves,
at real bash's own runtime, to a genuine `uv`). Before this fix, none of
this module's indirection machinery recognized this syntax at all -- not
merely mis-resolved, but contributing NOTHING to any rule's own
referenced-name/value collection, so a tool/verb/write-method hidden this
way was entirely invisible. Closed via `_resolve_indirect_ref` (used
directly by B1a/B1b and the gh-api flag-name sub-passes, and folded into
`_substitute_var_refs_candidates`'s own regex as a fourth alternative for
the gh-api value path) plus a new `_assigned_raw_values` map: the
first-level lookup needs NAME's assigned value as a CASE-PRESERVED key
into the second lookup (bash variable names are case-sensitive), so it
cannot reuse the existing `_assigned_literals`/`name_to_value` map, which
intentionally lowercases every RHS for this module's other, case-
insensitive tool/verb/write-method comparisons. The identical fix was
ported to the self-contained duplicate at
skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py,
which additionally had a fourth, unrelated tenth-round gap of its own:
`_rule_npx`/`_rule_bare_install`/`_rule_fetch_exec` previously checked
only a token's own literal text, with NO indirection handling of any
kind (`N=npx; $N left-pad` bypassed npx detection entirely) -- closed
there via a new unifying `_resolve_dynamic_token` helper (bare variable,
default clause, or `${!NAME}`, in that order) shared by all three rules.

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


# Matches a token that is EXACTLY one bash `${NAME:-default}`/
# `${NAME-default}`/`${NAME:=default}`/`${NAME=default}` construct
# (anchored -- the same "exactly one reference, nothing else" scoping
# `_BARE_VAR_RE` already applies to a bare reference) -- captures just the
# literal DEFAULT text, group 2. See _default_clause_literal below.
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
    round (issue #1326): none of `_rule_b1a_dynamic_word_same_segment_
    verb`/`_rule_b1b_dynamic_word_assigned_tool_and_verb` (both keyed off
    either a literal token text or a referenced variable's OWN assigned
    value) ever looked at a token's own embedded default-clause text, so
    this fully bypassed even the most basic install-verb detection."""
    match = _DEFAULT_CLAUSE_RE.match(token)
    return match.group(2) if match else None


# Matches a token that is EXACTLY bash's own `${!NAME}` indirect-reference
# syntax (anchored) -- unlike every other reference shape this module
# recognizes, bash requires the braces here; there is no unbraced `$!NAME`
# form (that parses as `$!` -- the last background job's PID -- followed by
# literal text "NAME"). See _resolve_indirect_ref below.
_INDIRECT_REF_RE = re.compile(r"^\$\{!([A-Za-z_][A-Za-z0-9_]*)\}$")


def _resolve_indirect_ref(token: str, name_to_value: dict[str, str], name_to_raw_value: dict[str, str]) -> str | None:
    """Resolve TOKEN's value when TOKEN is EXACTLY bash's own `${!NAME}`
    indirect-reference syntax -- a TWO-LEVEL lookup: NAME's own assigned
    value names a SECOND variable, and this expression evaluates to THAT
    variable's own assigned value. None if TOKEN is not this shape, or if
    either lookup level is unresolvable.

    The first-level lookup uses `name_to_raw_value` (case-preserved), not
    `name_to_value` (lowercased) -- NAME's value must be used as a
    case-correct KEY into the second lookup (bash variable names are
    case-sensitive: `TOOLREF=T; T=uv` must resolve via the key `"T"`, not
    a lowercased `"t"` that would miss it if no separate `t=` assignment
    exists). The second-level lookup uses `name_to_value` as usual, so the
    FINAL resolved value is still lowercased like every other resolution
    in this module.

    Found live by Step 8 independent review, tenth round (issue #1326):
    none of this module's existing indirection machinery (bare-reference
    lookup, default-clause extraction) ever recognized this bash syntax at
    all -- `${!TOOLREF}` contributed NOTHING to any rule's own
    referenced-name/value collection, so a tool/verb/write-method hidden
    this way was entirely invisible, not merely mis-resolved. Confirmed
    live via real bash argv expansion: `TOOLREF=T; T=uv; VERBREF=V;
    V=install; ${!TOOLREF} ${!VERBREF} foo` resolves to a genuine `uv
    install foo`, and `MREF=M; M=POST; gh api .../merge -X${!MREF}`
    resolves to a real `-XPOST` write."""
    match = _INDIRECT_REF_RE.match(token)
    if not match:
        return None
    referenced_name = name_to_raw_value.get(match.group(1))
    if referenced_name is None:
        return None
    return name_to_value.get(referenced_name)


# Matches one `$NAME`/`${NAME}`/`${NAME:-default}` reference anywhere in a
# token, capturing its full span (including the braces, when present) so
# _substitute_var_refs_candidates below can replace exactly that span --
# unlike _VAR_REF_RE, which only captures the name and is used solely to
# collect referenced names, never to reconstruct token text. The third
# alternative (default-clause) mirrors _DEFAULT_CLAUSE_RE above but is
# NOT anchored (`[^}]*` instead of `.*$`) -- it must stop at the first
# unescaped `}` so it can be found anywhere within a larger fused token
# (e.g. `-X${NEVER_SET-POST}`), not just when the construct is the whole
# token.
_VAR_REF_FULL_RE = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
    r"|\$\{([A-Za-z_][A-Za-z0-9_]*):?[-=]([^}]*)\}"
    r"|\$\{!([A-Za-z_][A-Za-z0-9_]*)\}"
    r"|\$([A-Za-z_][A-Za-z0-9_]*)"
)

# Safety valve for _substitute_var_refs_candidates' own combinatorial
# expansion (see its docstring) -- a bounded cap, not a silent truncation:
# exceeding it makes the caller treat the token as an unresolved-but-
# plausible match (fail closed), never as a quietly-dropped possibility.
_MAX_SUBSTITUTION_CANDIDATES = 64


def _unbraced_ref_options(name_run: str, name_to_value: dict[str, str]) -> list[str]:
    """Every sound reading of an UNBRACED `$NAME_RUN` reference, as a list
    of (resolved-value + leftover-literal-suffix) strings -- one per
    non-empty prefix of NAME_RUN that is actually assigned, longest
    prefix first. See _substitute_var_refs_candidates' own docstring for
    why more than the single longest-prefix reading is needed here."""
    return [
        name_to_value[name_run[:i]] + name_run[i:] for i in range(len(name_run), 0, -1) if name_run[:i] in name_to_value
    ]


def _substitute_var_refs_candidates(
    token: str, name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> list[str] | None:
    """Every sound reconstruction of TOKEN with each `$NAME`/`${NAME}`
    reference replaced by its assigned (already-lowercased) value,
    preserving any literal text around or between references -- e.g.
    `$M1$M2` with M1="po", M2="st" becomes "post". Returns `[]` (cannot
    resolve at all) if some reference has no assigned-and-in-range
    reading; returns `None` (too many readings to enumerate -- treat as
    unresolved but plausible, i.e. fail closed) if the combinatorial
    expansion below would exceed `_MAX_SUBSTITUTION_CANDIDATES`.

    A BRACED reference (`${M}`) is unambiguous -- the brace itself
    survives shlex's quote removal and unambiguously bounds the name --
    and contributes exactly one reading, same as the single-reading
    version this replaces. An UNBRACED reference (`$M`) is NOT
    unambiguous once shlex has already dequoted the token: `"$M"ST` (a
    quoted, bounded reference to `M` followed by literal `ST`) and
    `$MST` (a bare, unquoted reference to a variable literally named
    `MST`, bash's own maximal-munch parse) both dequote to the identical
    raw token text `$MST` -- shlex does not preserve which characters
    were inside the quotes. Found live by Step 8 independent review,
    eighth round (issue #1326): the prior single-greedy-match version of
    this function always assumed the maximal-munch (unquoted) reading,
    so `M=PO; gh api .../merge -X"$M"ST` -- a real `-XPOST` write once
    bash resolves it, confirmed via `bash -c` argv expansion -- was
    wrongly allowed, since "MST" was never itself assigned. Every
    non-empty prefix of an unbraced run that IS assigned is now tried as
    a candidate reading (`_unbraced_ref_options`), so a real write
    hidden behind either interpretation is still caught.

    Still bounded, not the unbounded recursive reconstruction the module
    docstring's graphql-mutation-keyword residual disclaims: `name_to_
    value`'s own entries are themselves already plain literal strings (a
    dynamic RHS is filtered out before ever entering `name_to_value` --
    see `_assigned_literals`), so this never re-expands a substituted
    value that might itself contain `$` -- it only branches over where
    one already-fixed identifier run might have been quote-bounded, a
    small, explicitly-capped enumeration.

    A `${NAME:-default}`/`${NAME-default}`/`${NAME:=default}`/
    `${NAME=default}` reference contributes the literal DEFAULT text as a
    candidate, PLUS NAME's own resolved value if NAME also happens to be
    assigned in this command (an extra safety-margin candidate: this
    classifier cannot know, at gate time, whether NAME will actually be
    unset/empty at bash's own real runtime -- an inherited environment
    variable is one example outside this classifier's own tracking).
    Found live by Step 8 independent review, ninth round (issue #1326):
    `gh api .../merge -X${TOTALLY_NEVER_MENTIONED-POST}` resolves (real
    bash, confirmed via argv expansion) to a real `-XPOST` write with NO
    variable assignment anywhere in the command at all -- the prior
    version of this function only ever recognized `$NAME`/`${NAME}`,
    never bash's own default-value expansion, so the entire construct was
    left as untouched literal text and never matched the write-method
    comparison. The DEFAULT text itself is not recursively re-scanned for
    further `$` references it might itself contain (e.g.
    `${UNSET:-$OTHER}`) -- a disclosed residual, the same "not the
    unbounded reconstruction problem" boundary this function already
    draws elsewhere, not attempted here.

    A `${!NAME}` reference (bash's own indirect reference -- see
    `_resolve_indirect_ref`'s own docstring for the two-level lookup and
    why it needs `name_to_raw_value` specifically) contributes NAME's
    doubly-resolved value as its one candidate, or no candidate at all if
    either lookup level fails. Found live by Step 8 independent review,
    tenth round (issue #1326): `MREF=M; M=POST; gh api .../merge
    -X${!MREF}` resolves (real bash, confirmed via argv expansion) to a
    real `-XPOST` write -- the prior version of this function never
    recognized this syntax at all, so the construct was left as untouched
    literal text, same class of gap as the ninth round's default-clause
    finding but a different bash feature."""
    partials = [""]
    pos = 0
    for match in _VAR_REF_FULL_RE.finditer(token):
        braced_name = match.group(1)
        default_name = match.group(2)
        default_text = match.group(3)
        indirect_name = match.group(4)
        if braced_name is not None:
            if braced_name not in name_to_value:
                return []
            options = [name_to_value[braced_name]]
        elif default_name is not None:
            options = [default_text]
            if default_name in name_to_value:
                options.append(name_to_value[default_name])
        elif indirect_name is not None:
            referenced_name = name_to_raw_value.get(indirect_name)
            resolved = name_to_value.get(referenced_name) if referenced_name is not None else None
            options = [resolved] if resolved is not None else []
        else:
            options = _unbraced_ref_options(match.group(5), name_to_value)
        if not options:
            return []
        if len(partials) * len(options) > _MAX_SUBSTITUTION_CANDIDATES:
            return None
        literal_before = token[pos : match.start()]
        partials = [p + literal_before + opt for p in partials for opt in options]
        pos = match.end()
    tail = token[pos:]
    return [p + tail for p in partials]


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


def _assigned_raw_values(tokens: list[str]) -> dict[str, str]:
    """Like `_assigned_literals`, but preserves the ORIGINAL case of each
    assignment's RHS value rather than lowercasing it -- needed for bash's
    own `${!NAME}` indirect-reference resolution (see
    `_resolve_indirect_ref`), where NAME's own assigned value must be used
    as a case-correct KEY into a second variable lookup (bash variable
    names are case-sensitive), not compared case-insensitively against a
    known tool/verb/write-method literal the way `_assigned_literals`'s
    own lowercased values are used everywhere else in this module."""
    values: dict[str, str] = {}
    for token in tokens:
        if _is_dynamic(token):
            continue
        match = _ASSIGN_RE.match(token)
        if match:
            values[match.group(1)] = match.group(2)
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
        # `_substitute_var_refs_candidates`'s reconstructed-string check below, which
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


def _write_method_candidate_hit(candidates: list[str] | None) -> bool:
    """True if any reading in CANDIDATES (from
    `_substitute_var_refs_candidates`) is a write method, OR CANDIDATES is
    None -- too many readings to enumerate soundly, so treated as an
    unresolved-but-plausible match rather than silently dropped (fail
    closed, matching this module's own established posture for a
    cannot-confidently-classify case)."""
    if candidates is None:
        return True
    return any(candidate.lower().startswith(method) for candidate in candidates for method in _WRITE_METHODS)


def _gh_api_method_dynamic_hit(
    seg: list[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
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
    round after the first fix landed. Resolved via
    `_substitute_var_refs_candidates` (not a per-variable value set):
    found live by Step 8 independent review, sixth round (issue #1326) --
    `-X "$M1$M2"` with `M1=PO`, `M2=ST` resolves to a real `POST` write
    once bash concatenates the two references, but checking each
    referenced variable's value separately (the prior approach) never
    recognized the concatenation, since neither "po" nor "st" alone is a
    write method. The reconstructed string is lowercased before
    comparison -- `_substitute_var_refs_candidates` preserves a token's
    literal text exactly as typed (only the substituted variable values
    are already-lowercased), so a literal fragment fused with a variable
    in the SAME token (`-X "PO$M"` with `M=ST`) reconstructs to "POst",
    not "post" -- found live by Step 8 independent review, seventh round
    (issue #1326): every existing test for this fix used a
    whole-variable-per-fragment split (`M1=PO; M2=ST`), which happens to
    already be all-lowercase after `_assigned_literals`'s own
    lowercasing, so this literal-fragment gap went unexercised. Every
    candidate reading `_substitute_var_refs_candidates` returns is
    checked (via `_write_method_candidate_hit`), not just one -- found
    live by Step 8 independent review, eighth round (issue #1326): an
    unbraced reference immediately followed by more identifier-shaped
    literal text (`-X"$M"ST` with `M=PO`) is itself ambiguous once shlex
    has dequoted it, see `_substitute_var_refs_candidates`'s own
    docstring. `name_to_raw_value` is threaded through purely to reach
    that function's own `${!NAME}` indirect-reference support (found live
    by Step 8 independent review, tenth round, issue #1326) -- this
    function itself has no direct use for it."""
    for i, raw_tok in enumerate(seg):
        dynamic_value_part = _gh_api_method_dynamic_value(seg, i, raw_tok)
        if dynamic_value_part is None:
            continue
        candidates = _substitute_var_refs_candidates(dynamic_value_part, name_to_value, name_to_raw_value)
        if _write_method_candidate_hit(candidates):
            return True
    return False


def _gh_api_method_flagname_dynamic_hit(
    seg: list[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
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
    none. The value token is resolved via `_substitute_var_refs_candidates`
    (not `_resolve_bare_var`), so a write-method value split across
    multiple concatenated variables (`$F "$M1$M2"`) is caught too -- the
    same gap `_gh_api_method_dynamic_hit` above had, found live by Step 8
    independent review, sixth round (issue #1326), against this
    function's own flag-name-indirection case. The resolved value is
    lowercased before comparison for the same reason as
    `_gh_api_method_dynamic_hit` above -- found live by Step 8
    independent review, seventh round (issue #1326): a literal fragment
    fused with a variable in the same value token (`$F "PO$M"` with
    `M=ST`) reconstructs to "POst", not "post". Every candidate reading is
    checked (via `_write_method_candidate_hit`), for the same
    unbraced-reference-ambiguity reason as `_gh_api_method_dynamic_hit`
    above -- found live by Step 8 independent review, eighth round (issue
    #1326). The flag-name token is ALSO resolved via
    `_resolve_indirect_ref` (bash's own `${!NAME}` syntax), not just
    `_resolve_bare_var` -- found live by Step 8 independent review, tenth
    round (issue #1326): `FREF=F; F=-X; gh api .../merge ${!FREF} POST`
    resolves (real bash) to a real `-X POST` write and was invisible to
    the bare-reference-only check."""
    for i, raw_tok in enumerate(seg):
        flag = _resolve_bare_var(raw_tok, name_to_value)
        if flag is None:
            flag = _resolve_indirect_ref(raw_tok, name_to_value, name_to_raw_value)
        if flag not in ("-x", "--method"):
            continue
        if i + 1 >= len(seg):
            continue
        value_tok = seg[i + 1]
        if _is_dynamic(value_tok):
            candidates = _substitute_var_refs_candidates(value_tok, name_to_value, name_to_raw_value)
            if _write_method_candidate_hit(candidates):
                return True
        elif any(value_tok.lower().startswith(m) for m in _WRITE_METHODS):
            return True
    return False


def _gh_api_method_fused_flagname_dynamic_hit(
    seg: list[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
    """The -X/--method flag NAME hidden behind a variable reference FUSED
    directly with its own value in the SAME token -- e.g. `F=-X; gh api
    .../merge "$F"POST` dequotes (shlex, like real bash, drops which
    characters were quoted) to the single token `$FPOST`. Neither prior
    fix's own shape recognizes this: `_gh_api_method_flagname_dynamic_hit`
    above requires the flag token to be a BARE, anchored single reference
    (`$F` alone, nothing fused after it); `_gh_api_method_dynamic_hit`
    requires a literal "-x"/"--method" TEXT prefix already present in the
    token before it ever looks for a dynamic value -- `$FPOST` starts
    with `$`, not that literal text. Found live by Step 8 independent
    review, eighth round (issue #1326), immediately after closing the
    plain quote-boundary-ambiguity case above: real bash (confirmed via
    `bash -c` argv expansion) resolves `F=-X; gh api .../merge "$F"POST`
    to a real `-XPOST` write.

    Every candidate reconstruction of the WHOLE token (via
    `_substitute_var_refs_candidates`, which already tries every sound
    quote-boundary reading) is checked against the same fused-flag shapes
    `_gh_api_method_literal_hit` already recognizes for a literal
    token -- this is not a new detection rule, only extending an existing
    one to dynamic tokens whose resolved reading was not knowable until
    substitution."""
    for raw_tok in seg:
        if not _is_dynamic(raw_tok):
            continue
        candidates = _substitute_var_refs_candidates(raw_tok, name_to_value, name_to_raw_value)
        if candidates is None:
            return True
        for candidate in candidates:
            lowered = candidate.lower()
            if (
                lowered.startswith("-x")
                and len(candidate) > 2
                and any(lowered[2:].startswith(m) for m in _WRITE_METHODS)
            ):
                return True
            if lowered.startswith("--method=") and any(
                lowered[len("--method=") :].startswith(m) for m in _WRITE_METHODS
            ):
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


def _gh_api_field_flagname_dynamic_hit(
    seg: list[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
    """Same class as `_gh_api_method_flagname_dynamic_hit`, for
    -f/-F/--field/--raw-field: the flag NAME itself hidden behind a bare
    variable reference (`FF=--field; gh api ... $FF name=value`). Unlike
    the method flag, this rule never inspects the field value -- presence
    of the flag alone is denied, matching `_gh_api_field_literal_hit`'s
    own scope. `-F` is not listed separately: `name_to_value`'s own
    values are already lowercased (`_assigned_literals`), so `FF=-F`
    resolves to `"-f"`, the same string `-f` itself lowercases to. Also
    resolved via `_resolve_indirect_ref` (bash's own `${!NAME}` syntax),
    not just `_resolve_bare_var` -- found live by Step 8 independent
    review, tenth round (issue #1326), the field-flag counterpart of
    `_gh_api_method_flagname_dynamic_hit`'s own tenth-round fix."""
    for raw_tok in seg:
        flag = _resolve_bare_var(raw_tok, name_to_value)
        if flag is None:
            flag = _resolve_indirect_ref(raw_tok, name_to_value, name_to_raw_value)
        if flag in ("-f", "--field", "--raw-field"):
            return True
    return False


def _gh_api_field_fused_flagname_dynamic_hit(
    seg: list[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
    """The field-flag counterpart of
    `_gh_api_method_fused_flagname_dynamic_hit`: the -f/--field/--raw-field
    flag NAME hidden behind a variable reference FUSED directly with its
    own value in the SAME token -- e.g. `FF=-f; gh api ... "$FF"name=value`
    dequotes to the single token `$FFname=value`. Found live by Step 8
    independent review, eighth round (issue #1326), immediately after the
    method-flag sibling above: real bash resolves
    `FF=-f; gh api .../1 "$FF"name=value` to a real `-fname=value` field
    write. Unlike the method flag, this rule never inspects the field
    value -- presence of the flag alone is denied, matching
    `_gh_api_field_literal_hit`'s own scope."""
    for raw_tok in seg:
        if not _is_dynamic(raw_tok):
            continue
        candidates = _substitute_var_refs_candidates(raw_tok, name_to_value, name_to_raw_value)
        if candidates is None:
            return True
        for candidate in candidates:
            lowered = candidate.lower()
            if lowered.startswith("-f") and len(candidate) > 2:
                return True
            if lowered.startswith("--field=") or lowered.startswith("--raw-field="):
                return True
    return False


def _rule_gh_api_write(
    segments: list[list[str]], lowered_command: str, name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> str | None:
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
        if _gh_api_method_dynamic_hit(seg, name_to_value, name_to_raw_value):
            return _METHOD_FLAG_DYNAMIC_HIT
        if _gh_api_method_flagname_dynamic_hit(seg, name_to_value, name_to_raw_value):
            return _METHOD_FLAG_DYNAMIC_HIT
        if _gh_api_method_fused_flagname_dynamic_hit(seg, name_to_value, name_to_raw_value):
            return _METHOD_FLAG_DYNAMIC_HIT

        if not has_graphql:
            if _gh_api_field_literal_hit(literals):
                return _FIELD_FLAG_HIT
            if _gh_api_field_dynamic_hit(seg):
                return _FIELD_FLAG_HIT
            if _gh_api_field_flagname_dynamic_hit(seg, name_to_value, name_to_raw_value):
                return _FIELD_FLAG_HIT
            if _gh_api_field_fused_flagname_dynamic_hit(seg, name_to_value, name_to_raw_value):
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


def _rule_b1a_dynamic_word_same_segment_verb(
    seg: list[str], verb_set: set[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
    """A segment whose command word is dynamic, with a literal watched-verb
    token present anywhere else in that SAME segment (e.g.
    `$T install foo` -- `install` sits right there). Scoped to one segment
    on purpose, so it cannot combine with an unrelated verb-shaped word in
    a different, unrelated segment.

    A verb hidden in a `${NEVER_SET:-install}`-shaped token's own DEFAULT
    text counts too (via `_default_clause_literal`), not just a plain
    literal token -- found live by Step 8 independent review, ninth round
    (issue #1326): `${NEVER_SET:-uv} ${NEVER_SET2:-install} foo` fully
    bypassed this rule (and B1b below) before this fix, needing NO
    variable assignment anywhere in the command at all. A verb hidden
    behind bash's own `${!NAME}` indirect reference (via
    `_resolve_indirect_ref`) counts too -- found live by Step 8
    independent review, tenth round (issue #1326): `TOOLREF=T; T=uv;
    VERBREF=V; V=install; ${!TOOLREF} ${!VERBREF} foo` fully bypassed
    this rule (and B1b below) before this fix."""
    if not seg or not _is_dynamic(seg[0]):
        return False
    literals = {t.lower() for t in seg[1:] if not _is_dynamic(t)}
    for tok in seg[1:]:
        default_text = _default_clause_literal(tok)
        if default_text is not None:
            literals.add(default_text.lower())
        indirect_value = _resolve_indirect_ref(tok, name_to_value, name_to_raw_value)
        if indirect_value is not None:
            literals.add(indirect_value.lower())
    return bool(literals & verb_set)


def _rule_b1b_dynamic_word_assigned_tool_and_verb(
    seg: list[str], name_to_value: dict[str, str], verb_set: set[str], name_to_raw_value: dict[str, str]
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
    no dynamic command at all.

    A tool or verb embedded directly as a `${NEVER_SET:-uv}`-shaped
    token's own DEFAULT text (via `_default_clause_literal`) counts as a
    "value" here too, alongside a referenced variable's own assigned
    value -- found live by Step 8 independent review, ninth round (issue
    #1326), the same finding as `_rule_b1a_dynamic_word_same_segment_
    verb`'s own fix above: `${NEVER_SET:-uv} ${NEVER_SET2:-install} foo`
    resolves (real bash) to a genuine `uv install foo` with no `NAME=`
    assignment anywhere in the command, and was wrongly allowed since
    neither `NEVER_SET` nor `NEVER_SET2` was ever assigned for the
    prior, assignment-only version of this rule to look up. A tool or
    verb hidden behind bash's own `${!NAME}` indirect reference (via
    `_resolve_indirect_ref`) counts too -- found live by Step 8
    independent review, tenth round (issue #1326): see
    `_rule_b1a_dynamic_word_same_segment_verb`'s own tenth-round fix."""
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
        indirect_value = _resolve_indirect_ref(tok, name_to_value, name_to_raw_value)
        if indirect_value is not None:
            values.add(indirect_value.lower())
    if not referenced and not values:
        return False
    values |= {name_to_value[name] for name in referenced if name in name_to_value}
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
    raw_assigned = _assigned_raw_values(tokens)
    lowered_command = command.lower()

    is_git_push = any(_is_git_push_segment(seg) for seg in segments)

    literal_hit = _rule_a_literal(segments)
    if literal_hit:
        return Verdict(True, literal_hit, is_git_push)

    gh_api_hit = _rule_gh_api_write(segments, lowered_command, assigned, raw_assigned)
    if gh_api_hit:
        return Verdict(True, gh_api_hit, is_git_push)

    for seg in segments:
        if _rule_b1a_dynamic_word_same_segment_verb(seg, _WATCHED_VERBS, assigned, raw_assigned):
            return Verdict(
                True,
                "a Bash command word is dynamically constructed, alongside a denied verb literally "
                "present in the same command -- rewrite as a plain literal command so it can be checked",
                is_git_push,
            )
        if _rule_b1b_dynamic_word_assigned_tool_and_verb(seg, assigned, _WATCHED_VERBS, raw_assigned):
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
            _rule_b1a_dynamic_word_same_segment_verb(seg, {_GIT_PUSH_VERB}, assigned, raw_assigned)
            or _rule_b1b_dynamic_word_assigned_tool_and_verb(seg, assigned, {_GIT_PUSH_VERB}, raw_assigned)
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

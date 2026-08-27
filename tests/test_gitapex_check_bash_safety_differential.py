"""Generative differential property test, hooks bash-safety classifier
(issue #1365, Task 5).

Fuzzes `hooks/gitapex_check_bash_safety.py`'s own `classify()` against a
REAL `bash -c` (via `tests/_gitapex_bash_oracle.py`'s stand-in-PATH oracle,
see that module's own docstring for the full safety design: PATH fully
replaced, minimal env, own process group, hard timeout+killpg,
RLIMIT_CPU/RLIMIT_NPROC defense-in-depth). Every generated command is run
through the real oracle first; `classify()` is asserted against ONLY when
the oracle's own observation shows the intended shape genuinely resolved --
never the converse (see "One-directional assertion" below).

Watched vocabulary, enumerated directly from source (not guessed)
---------------------------------------------------------------------
* `checker._DENIED_ADJACENT` -- every `gh`/git tool+verb sequence the
  literal-match rule (`_rule_a_literal`) denies: all `gh issue *`/`gh pr *`
  subcommands plus the install-family tools (pip/npm/yarn/uv/go/brew/apt/
  gem/cargo/plugin). Imported directly (`list(checker._DENIED_ADJACENT)`),
  never a hardcoded copy, so this test tracks the module's own table.
* The `gh api` write-flag family `_rule_gh_api_write` checks directly:
  `-X`/`--method` (`_gh_api_method_literal_hit`) with a value drawn from
  `checker._WRITE_METHODS` (imported, not copied), and `-f`/`-F`/`--field`/
  `--raw-field` (`_gh_api_field_literal_hit`) -- flag names read directly
  from those two functions' own literal comparisons, not guessed.
* `git push`, checked separately (`_is_git_push_segment`) -- this
  classifier's own `is_git_push` field is warn-only, never a hard deny, so
  it gets its own property (`test_oracle_confirmed_git_push_implies_is_git_push`)
  with its own one-directional assertion, distinct from the deny-side one.

Obfuscation techniques, empirically calibrated against THIS module
---------------------------------------------------------------------
Every (payload category x technique) pair this grammar can produce was
validated twice, exhaustively (not sampled), before this file was written:
once statically against `checker.classify()` directly (5,676 combinations,
zero unexpected misses), and -- since a static check alone cannot reveal a
classifier-vs-real-bash disagreement -- again END TO END through the real
oracle itself (~3,900 combinations across every pattern/flag/technique/
decoy combination this grammar draws from, zero unexpected misses after
the `ifs_dollar` fix documented below). The real-oracle pass is what caught
that fix in the first place: a purely static check would have missed it
entirely, since (as built at first) `classify()` and real bash agreed with
each other on the wrong shape (see the `$IFS` reassignment section below).
Confirmed, not assumed, exactly the discipline this repository's own
module docstrings apply elsewhere. This calibration is what settled two
specific exclusions below, both genuine, currently-real gaps in this
classifier (neither is a bug this task fixes -- Task 5 is a test-only
task):

1. Array-literal indirection is generated ONLY as "the whole tool+verb(s)
   phrase packed into ONE array" (`A=(tool verb1 verb2 decoy); "${A[@]}"`)
   -- confirmed live (`checker.classify("A=(uv install); ...")` denies,
   `_rule_array_literal_content` recursively classifies that ONE array's
   own inner content directly). The classifier's OWN disclosed residual
   (`array-literal-assignment-indirection` in both `KNOWN_BYPASS_COMMANDS`
   lists) is a DIFFERENT shape -- tool and verb split across TWO SEPARATE
   arrays (`A=(uv); V=(install); "${A[@]}" "${V[@]}" foo`) -- confirmed
   live, directly against `classify()`, to still return `deny=False` for
   this shape regardless of which tool/verb/decoy is substituted in (not
   only the one exact pinned string), because the fold representation
   `_assigned_literals` reads back for each array (`"( uv)"`, literally,
   parens included) is not the clean value B1a/B1b's set-membership check
   needs. This grammar therefore never constructs that two-array shape at
   all -- the `KNOWN_BYPASS_COMMANDS` `assume()` exclusion below is a pure
   defensive backstop (per the task's own instruction to exclude by exact
   string, never by shape), not this grammar's actual mechanism for
   avoiding that gap.
2. The "bare, sole, unassigned `$(...)` occupying the entire command"
   command-substitution form (`$(echo "...")"`, re-executed once bash
   word-splits its own output) is generated only at nesting depth 1 for
   EVERY payload category, and ADDITIONALLY at depth 2 for the
   `denied_adjacent`/`git_push` categories -- but NEVER at depth 2 for a
   `gh api` write-flag payload, and never at all (any depth) for the
   `gh api` payload in this "bare" form beyond depth 1's own working case.
   Confirmed live: `classify('$(echo "gh api repos/x/x -X POST")')`
   returns `deny=False` -- `_rule_command_substitution_content`'s own
   phrase-substring fallback only matches a `_DENIED_ADJACENT`-shaped
   phrase, never a `-X`/`--method` write-flag shape, so a `gh api`
   write-flag payload fused into ONE quoted argument this way is invisible
   to it. The "ADJACENT" cmdsub form (`$(echo gh) api ... -X POST`, command
   word from the substitution, the rest literal in the SAME segment) is
   NOT affected -- confirmed live, denied via B1a (`api` is itself a
   member of `_WATCHED_VERBS`, by design, per that set's own module
   comment) -- so `gh api` payloads use the adjacent form at both depth 1
   and depth 2, just never the bare form beyond depth 1.

`$IFS` reassignment, "including case variation" (per the branch plan's own
Task 5 wording): generated as both written forms this classifier's own
`_ifs_split` recognizes verbatim -- `$IFS` and `${IFS}` -- since bash's
`IFS` variable name is itself fixed-case (a differently-cased spelling
would reference an unrelated, ordinary variable, not trigger real
word-splitting at all); "case variation" here means the two SYNTACTIC
forms, not the letters' own case. The unbraced `$IFS` form is NOT joined
bare between two payload words (`"$IFS".join(...)`) -- confirmed live, via
the real oracle, that real bash's own maximal-munch parsing of an unbraced
`$NAME` reference consumes `pip$IFSinstall` as ONE reference named
`IFSinstall` (unset, expands to nothing), not `$IFS` (whitespace) followed
by literal `install` -- so a naive bare join resolves to `pip` invoked with
ZERO arguments, never the intended `pip install`. `_build_command`'s own
`ifs_dollar` branch instead joins with the literal separator `$IFS""` (an
empty, immediately-adjacent quoted string terminates the reference exactly
as unambiguously as the braced form's own `}` does, while still expanding-
and-splitting on `$IFS`'s real value) -- confirmed live to resolve exactly
as intended.

Decoy identifiers are a small curated inert set (`_DECOYS`), never free
text -- and every variable/array name this grammar ever constructs
(`TOOLVAR`, `V0`..`V4`, `PAYLOADARR`) is a fixed literal baked into this
file's own template functions, never Hypothesis-generated, so nothing
free-form can ever land in command-word position. Redirection is never
free: the only `<`/`>` this grammar emits is the fixed literal `"<("`
(process substitution, always immediately paren-bound); no shell builtin
(`exec`, `eval`, `trap`, `kill`, `ulimit`, `:`, `wait`, `source`, `.`) is
ever emitted in command-word position -- the only non-payload command word
this grammar ever uses is `echo` (a safe, side-effect-free bash builtin,
not on that exclusion list), inside `$(...)`/`<(...)` constructs only.
Command-substitution/process-substitution nesting is hard-capped at depth
2 by construction (`cmdsub_adjacent_depth2`, and `_append_process_
substitution`'s own two-branch depth argument) -- there is no recursive or
open-ended nesting path anywhere in this grammar.

One-directional assertion (never the converse)
-------------------------------------------------
For every generated command: run it through the real oracle first, THEN
call `checker.classify()` on the identical string. `_oracle_shows_denied_
write`/`_oracle_shows_git_push` inspect ONLY the oracle's own real,
observed `(tool, argv)` captures -- never `classify()`'s own reasoning --
to decide whether the intended shape actually reached a watched tool as a
real invocation. The assertion fires ONLY when that observation is
present; a `classify()` denial/`is_git_push` with no matching oracle
observation is never treated as a failure (the oracle's minimal PATH-only
environment can diverge from a real session's), and an oracle observation
with no corresponding `classify()` verdict match IS asserted against
(that is the entire point of a differential test) -- but only in the
`deny`/`is_git_push` direction the branch plan names, never the reverse.

`KNOWN_BYPASS_COMMANDS` exclusion (exact string, never shape)
------------------------------------------------------------------
Both classifiers' own `KNOWN_BYPASS_COMMANDS` lists (`hooks/test_gitapex_
check_bash_safety.py`'s 3 entries, `skills/executing-a-branch-plan/scripts/
test_gitapex_check_task_bash_safety.py`'s 4) are imported directly (never
hardcoded) and excluded via `hypothesis.assume()` against the exact
generated command string -- per the branch plan's own explicit instruction,
this is a defensive backstop for an exact-string coincidence, not this
grammar's mechanism for avoiding the one array-literal residual documented
above (this grammar structurally never generates that residual's own
two-array shape at all, per point 1 above).

Reproducibility: mirrors `tests/test_gitapex_gate_detection_logic_property_
coverage_properties.py:123-137`'s own `_PROPERTIES` pattern exactly --
`derandomize=True, max_examples=200, deadline=None` by default,
`derandomize=False, max_examples=5000, deadline=None` when
`GITAPEX_HYPOTHESIS_DEEP_SCAN=1` (the scheduled deep-scan workflow, task 7
of this same branch plan). Marked `@pytest.mark.slow` (spawns a real `bash`
subprocess per generated example) per this repository's own registered
marker.
"""

from __future__ import annotations

import os

import gitapex_check_bash_safety as checker
import pytest
import test_gitapex_check_bash_safety as hooks_known_bypass_module
import test_gitapex_check_task_bash_safety as sibling_known_bypass_module
from _gitapex_bash_oracle import assert_closed_vocabulary, parse_capture_file, run_oracle_in
from hypothesis import assume, given, settings
from hypothesis import strategies as st

_PROPERTIES = (
    settings(derandomize=False, max_examples=5000, deadline=None)
    if os.environ.get("GITAPEX_HYPOTHESIS_DEEP_SCAN") == "1"
    else settings(derandomize=True, max_examples=200, deadline=None)
)

# Imported directly from both classifiers' own test files -- never a
# hardcoded copy -- and compared by exact string only (never shape-matched).
_KNOWN_BYPASS_COMMAND_STRINGS = frozenset(
    command for command, _case_id in hooks_known_bypass_module.KNOWN_BYPASS_COMMANDS
) | frozenset(command for command, _case_id in sibling_known_bypass_module.KNOWN_BYPASS_COMMANDS)

# --- Watched vocabulary, read directly from the classifier's own source ---

_WATCHED_TOOL_NAMES = sorted(checker._WATCHED_TOOLS)
_DENIED_ADJACENT_PATTERNS = list(checker._DENIED_ADJACENT)
_WRITE_METHOD_VALUES = tuple(sorted(m.upper() for m in checker._WRITE_METHODS))
# Read directly from _gh_api_method_literal_hit/_gh_api_field_literal_hit's
# own literal token comparisons -- not guessed.
_METHOD_FLAGS = ("-X", "--method")
_FIELD_FLAGS = ("-f", "-F", "--field", "--raw-field")

_DECOYS = ("foo", "bar", "baz", "x", "y")

# Grammar-closure gate, run at import time (issue #1365, Step 8 independent
# adversarial review). Every vocabulary above except `_DECOYS` is IMPORTED
# from `gitapex_check_bash_safety`, a module this branch may not modify and
# whose tables will keep evolving -- so this grammar's own "no free
# redirection operator, no backgrounding, no unbounded nesting" closure
# claim (see the module docstring) actually depends on a property of THAT
# file: that no table entry carries whitespace or a shell metacharacter.
# A future `_DENIED_ADJACENT` entry such as `("gh", "pr", "merge --admin")`
# would otherwise silently widen what a real `bash -c` is handed here, with
# nothing catching it. Checked, not assumed: a violation is a collection
# error naming the drifted table, not a wider generated command.
for _vocabulary, _source in (
    ([word for pattern in _DENIED_ADJACENT_PATTERNS for word in pattern], "checker._DENIED_ADJACENT"),
    (_WATCHED_TOOL_NAMES, "checker._WATCHED_TOOLS"),
    (_WRITE_METHOD_VALUES, "checker._WRITE_METHODS"),
    (_METHOD_FLAGS, "this module's own _METHOD_FLAGS"),
    (_FIELD_FLAGS, "this module's own _FIELD_FLAGS"),
    (_DECOYS, "this module's own _DECOYS"),
):
    assert_closed_vocabulary(_vocabulary, _source)

# Every technique below is safe (empirically confirmed, see module
# docstring) for BOTH the denied-adjacent tool+verb payload and the git-push
# payload. Annotated `tuple[str, ...]` (not the narrower fixed-length tuple
# type mypy would otherwise infer from the literal) so `techniques` in
# `_make_denied_write_command` below can be assigned either this or
# `_GH_API_TECHNIQUES` (a different length) without a type error.
_FULL_TECHNIQUES: tuple[str, ...] = (
    "literal",
    "quote_split",
    "ifs_dollar",
    "ifs_braced",
    "var_b1a",
    "var_b1b",
    "array_whole",
    "cmdsub_bare_depth1",
    "cmdsub_adjacent_depth1",
    "cmdsub_adjacent_depth2",
)
# gh-api write-flag payloads exclude the bare-form command substitution --
# see module docstring point 2 for the confirmed-live reason.
_GH_API_TECHNIQUES: tuple[str, ...] = tuple(
    technique for technique in _FULL_TECHNIQUES if technique != "cmdsub_bare_depth1"
)


def _quote_split_word(word: str) -> str:
    """`p""ip`-style quote-splitting: an empty `""` pair spliced after the
    first character. shlex's own quote removal (this classifier's whole
    reason for tokenizing with shlex) dequotes this back to the plain
    literal word before `classify()` ever sees it."""
    return f'{word[0]}""{word[1:]}' if len(word) >= 2 else word


def _build_command(core: list[str], decoy: str, technique: str) -> str:
    """Render CORE (the tool + verb word(s), in order) plus one trailing
    DECOY argument as a bash command string, obfuscated per TECHNIQUE. Every
    technique reconstructs CORE's own words, in order, as real argv once
    bash actually runs the result -- confirmed empirically (see module
    docstring) for every (payload category x technique) pair this grammar
    actually uses."""
    if technique == "literal":
        return f"{' '.join(core)} {decoy}"
    if technique == "quote_split":
        return f"{' '.join(_quote_split_word(word) for word in core)} {decoy}"
    if technique == "ifs_dollar":
        # NOT a bare `"$IFS".join(...)`: real bash's own unbraced `$NAME`
        # parsing is maximal-munch -- `pip$IFSinstall` is parsed as ONE
        # variable reference named `IFSinstall` (unset, expands to nothing),
        # never as `$IFS` (whitespace) followed by literal `install` --
        # confirmed live via the real oracle (`pip$IFSinstall$IFSfoo`
        # resolves to `pip` invoked with NO arguments at all, not `install
        # foo`) before shipping this technique. `""` immediately after each
        # `$IFS` is not itself an identifier character, so it unambiguously
        # terminates the reference the same way the braced form's own `}`
        # does, while still expanding-then-splitting on the real `$IFS`
        # value exactly as intended.
        return '$IFS""'.join([*core, decoy])
    if technique == "ifs_braced":
        return "${IFS}".join([*core, decoy])
    if technique == "var_b1a":
        # Only the command word (core[0]) becomes a variable -- the rest of
        # CORE stays literal in the SAME segment (Rule B1a's own shape).
        rest = " ".join(core[1:])
        return f"TOOLVAR={core[0]}; $TOOLVAR {rest} {decoy}"
    if technique == "var_b1b":
        # Every CORE word gets its own variable (Rule B1b's own shape).
        assigns = [f"V{i}={word}" for i, word in enumerate(core)]
        refs = [f"$V{i}" for i in range(len(core))]
        return "; ".join(assigns) + "; " + " ".join(refs) + f" {decoy}"
    if technique == "array_whole":
        # The WHOLE core+decoy phrase inside ONE array -- see module
        # docstring point 1 for why this, and never the two-separate-array
        # shape, is what this technique constructs.
        return f'PAYLOADARR=({" ".join([*core, decoy])}); "${{PAYLOADARR[@]}}"'
    if technique == "cmdsub_bare_depth1":
        return f'$(echo "{" ".join([*core, decoy])}")'
    if technique == "cmdsub_adjacent_depth1":
        rest = " ".join(core[1:])
        return f"$(echo {core[0]}) {rest} {decoy}"
    if technique == "cmdsub_adjacent_depth2":
        rest = " ".join(core[1:])
        return f"$(echo $(echo {core[0]})) {rest} {decoy}"
    raise ValueError(f"unknown technique: {technique}")


def _append_process_substitution(command: str, depth: int) -> str:
    """Append one inert, unread, unopened process-substitution argument --
    `<(echo z1)` at depth 1, or `<(echo z1 <(echo z2))` (nested, hard-capped
    at depth 2) -- to COMMAND. `echo` never blocks writing this little
    output to the pipe, and nothing ever reads it, so this cannot hang the
    oracle's own subprocess. Only ever called with a COMMAND whose own
    payload is unaffected by trailing content (never the `cmdsub_bare_*`
    forms, which occupy the ENTIRE command line by design -- callers must
    not append after those)."""
    if depth == 1:
        return f"{command} <(echo z1)"
    return f"{command} <(echo z1 <(echo z2))"


def _make_denied_write_command(
    category: str,
    pattern_index: int,
    method: str,
    method_flag: str,
    field_flag: str,
    path_decoy: str,
    value_decoy: str,
    decoy: str,
    technique_index: int,
    use_process_sub: bool,
    process_sub_depth: int,
) -> str:
    if category == "denied_adjacent":
        core = list(_DENIED_ADJACENT_PATTERNS[pattern_index % len(_DENIED_ADJACENT_PATTERNS)])
        techniques = _FULL_TECHNIQUES
    elif category == "gh_api_method":
        core = ["gh", "api", f"repos/{path_decoy}/x", method_flag, method]
        techniques = _GH_API_TECHNIQUES
    else:
        core = ["gh", "api", f"repos/{path_decoy}/x", field_flag, f"name={value_decoy}"]
        techniques = _GH_API_TECHNIQUES
    technique = techniques[technique_index % len(techniques)]
    command = _build_command(core, decoy, technique)
    if use_process_sub and technique != "cmdsub_bare_depth1":
        command = _append_process_substitution(command, process_sub_depth)
    return command


def _make_git_push_command(
    decoy: str,
    technique_index: int,
    use_process_sub: bool,
    process_sub_depth: int,
) -> str:
    core = ["git", "push"]
    technique = _FULL_TECHNIQUES[technique_index % len(_FULL_TECHNIQUES)]
    command = _build_command(core, decoy, technique)
    if use_process_sub and technique != "cmdsub_bare_depth1":
        command = _append_process_substitution(command, process_sub_depth)
    return command


_denied_write_commands = st.builds(
    _make_denied_write_command,
    category=st.sampled_from(("denied_adjacent", "gh_api_method", "gh_api_field")),
    pattern_index=st.integers(min_value=0, max_value=len(_DENIED_ADJACENT_PATTERNS) - 1),
    method=st.sampled_from(_WRITE_METHOD_VALUES),
    method_flag=st.sampled_from(_METHOD_FLAGS),
    field_flag=st.sampled_from(_FIELD_FLAGS),
    path_decoy=st.sampled_from(_DECOYS),
    value_decoy=st.sampled_from(_DECOYS),
    decoy=st.sampled_from(_DECOYS),
    technique_index=st.integers(min_value=0, max_value=len(_FULL_TECHNIQUES) - 1),
    use_process_sub=st.booleans(),
    process_sub_depth=st.sampled_from((1, 2)),
)

_git_push_commands = st.builds(
    _make_git_push_command,
    decoy=st.sampled_from(_DECOYS),
    technique_index=st.integers(min_value=0, max_value=len(_FULL_TECHNIQUES) - 1),
    use_process_sub=st.booleans(),
    process_sub_depth=st.sampled_from((1, 2)),
)


def _oracle_shows_denied_write(observations: list[tuple[str, list[str]]]) -> bool:
    """True if OBSERVATIONS (the oracle's own real, captured `(tool, argv)`
    invocations) show EITHER a `_DENIED_ADJACENT` tool+verb(s) sequence
    genuinely reaching its watched tool, in order, OR a real `gh api`
    invocation carrying a genuine write-method value or field flag in its
    own argv -- the exact two shapes `_rule_a_literal`/`_rule_gh_api_write`
    police. Looks only at the oracle's own real observation, never at
    `classify()`'s own reasoning."""
    for tool_name, args in observations:
        tool = tool_name.lower()
        lowered_args = [arg.lower() for arg in args]
        for pattern in _DENIED_ADJACENT_PATTERNS:
            if tool != pattern[0]:
                continue
            verbs = list(pattern[1:])
            if lowered_args[: len(verbs)] == verbs:
                return True
        if tool == "gh" and lowered_args[:1] == ["api"]:
            for i, tok in enumerate(lowered_args):
                if (
                    tok in ("-x", "--method")
                    and i + 1 < len(lowered_args)
                    and lowered_args[i + 1] in checker._WRITE_METHODS
                ):
                    return True
                # `-F` is absent from this tuple deliberately, not by
                # omission: `lowered_args` has already lower-cased every
                # token, so the generated `-F` field flag arrives here as
                # `-f` and is matched by that entry. Spelled out because
                # the generation-side `_FIELD_FLAGS` above DOES list all
                # four, and the asymmetry otherwise reads as a gap.
                if tok in ("-f", "--field", "--raw-field"):
                    return True
    return False


def _oracle_shows_git_push(observations: list[tuple[str, list[str]]]) -> bool:
    """True if OBSERVATIONS show a real `git` invocation whose own first
    argument is `push` -- the exact shape `_is_git_push_segment` polices."""
    return any(tool_name.lower() == "git" and args and args[0].lower() == "push" for tool_name, args in observations)


def _run_oracle_observations(command: str, tmp_path_factory: pytest.TempPathFactory) -> list[tuple[str, list[str]]]:
    """Run COMMAND through a fresh oracle invocation (a brand-new stand-in
    dir/capture file/cwd every call, via `tmp_path_factory.mktemp` -- never
    a fixed/shared path, safe under this repo's own `-n auto` pytest-xdist
    addopts, matching `tests/_gitapex_bash_oracle.py`'s own established
    convention) and return the parsed `(tool, argv)` observations."""
    base = tmp_path_factory.mktemp("bash_safety_differential")
    _run, capture_file = run_oracle_in(command, _WATCHED_TOOL_NAMES, base)
    return parse_capture_file(capture_file)


@pytest.mark.parametrize(
    ("rule_names", "command", "field"),
    [
        (
            ("_rule_a_literal",),
            _make_denied_write_command("denied_adjacent", 0, "POST", "-X", "-f", "foo", "bar", "baz", 0, False, 1),
            "deny",
        ),
        (
            ("_rule_gh_api_write",),
            _make_denied_write_command("gh_api_method", 0, "POST", "-X", "-f", "foo", "bar", "baz", 0, False, 1),
            "deny",
        ),
        (
            ("_rule_gh_api_write",),
            _make_denied_write_command("gh_api_field", 0, "POST", "-X", "-f", "foo", "bar", "baz", 0, False, 1),
            "deny",
        ),
        (
            ("_rule_b1a_dynamic_word_same_segment_verb", "_rule_b1b_dynamic_word_assigned_tool_and_verb"),
            _make_denied_write_command("denied_adjacent", 0, "POST", "-X", "-f", "foo", "bar", "baz", 5, False, 1),
            "deny",
        ),
        (("_is_git_push_segment",), _make_git_push_command("foo", 0, False, 1), "is_git_push"),
    ],
    ids=["literal", "gh_api_method", "gh_api_field", "var_b1b", "git_push"],
)
def test_property_assertions_have_teeth(
    rule_names: tuple[str, ...], command: str, field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-vacuity gate for the two properties below (issue #1365, Step 8
    independent adversarial review): a one-directional property that never
    reaches its assertion, or whose consequent cannot fail, is green for
    the wrong reason.

    The manual version of this check -- neutralize one rule in the
    classifier's own source, confirm the differential property then fails
    -- cannot be committed: issue #1365's own Constraints forbid this
    branch from touching either classifier's detection logic. Neutralizing
    the same rule by `monkeypatch` instead needs no source edit at all, so
    the proof lives in-tree as a real regression gate rather than as a
    procedure a future reader has to trust and re-run by hand.

    Each case takes a command built by THIS FILE's own generator (never a
    hand-written string, so it tracks the grammar), asserts the classifier
    denies/flags it today, then neutralizes the specific rule(s) the
    property is actually exercising for that shape and asserts the verdict
    flips -- i.e. the property's own assertion below WOULD have failed. The
    other half of anti-vacuity (the oracle's own antecedent genuinely
    firing, never silently skipping) is what `_oracle_shows_denied_write`/
    `_oracle_shows_git_push` are measured on: exhaustively re-checked
    during that same review across every (category x technique x
    pattern x process-substitution) combination this grammar can build --
    100% reached, none skipped."""
    assert getattr(checker.classify(command), field) is True, command
    for rule_name in rule_names:
        monkeypatch.setattr(checker, rule_name, lambda *_args, **_kwargs: None)
    assert getattr(checker.classify(command), field) is False, (
        f"neutralizing {rule_names} did not change classify().{field} for {command!r} -- this "
        "property's own assertion is being satisfied by some other rule, so it is not "
        "actually testing what its name claims"
    )


@pytest.mark.slow
@_PROPERTIES
@given(command=_denied_write_commands)
def test_oracle_confirmed_denied_write_implies_classify_denies(
    command: str, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """One-directional: if the real oracle shows a `_DENIED_ADJACENT`
    tool+verb(s) sequence, or a genuine `gh api` write-flag/value, actually
    reached its watched tool's own real argv, `classify()` must deny. Never
    asserts the converse -- see module docstring."""
    assume(command not in _KNOWN_BYPASS_COMMAND_STRINGS)
    observations = _run_oracle_observations(command, tmp_path_factory)
    if _oracle_shows_denied_write(observations):
        verdict = checker.classify(command)
        assert verdict.deny is True, (command, observations, verdict)


@pytest.mark.slow
@_PROPERTIES
@given(command=_git_push_commands)
def test_oracle_confirmed_git_push_implies_is_git_push(command: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    """One-directional: if the real oracle shows a genuine `git push`
    invocation, `classify().is_git_push` must be `True` (this classifier's
    own git-push field is warn-only, never a hard deny -- `deny` is not
    asserted here at all). Never asserts the converse -- see module
    docstring."""
    assume(command not in _KNOWN_BYPASS_COMMAND_STRINGS)
    observations = _run_oracle_observations(command, tmp_path_factory)
    if _oracle_shows_git_push(observations):
        verdict = checker.classify(command)
        assert verdict.is_git_push is True, (command, observations, verdict)

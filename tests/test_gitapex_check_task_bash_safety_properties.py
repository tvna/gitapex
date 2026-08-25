"""Hypothesis property-based layer for
``skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py``'s
detection-logic call sites (issue #1178's
``detection-logic-property-coverage`` gate; issue #1326 Stage 1 added this
module -- a self-contained duplicate of ``hooks/gitapex_check_bash_safety.py``
adapted for the task-agent-scoped policy -- with zero property coverage of
its own regex/string-comparison call sites).

Resolves via ``import gitapex_check_task_bash_safety`` against
``skills/executing-a-branch-plan/scripts`` specifically (this repository's
own ``pyproject.toml`` ``pythonpath`` entry) -- the sibling module at
``hooks/gitapex_check_bash_safety.py`` is covered by its own separate
properties file (``test_gitapex_check_bash_safety_properties.py``), since
the two are self-contained duplicates, not a shared module (see this
module's own docstring for why: no skill shares a ``scripts/`` directory
with another).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import string

import gitapex_check_task_bash_safety as checker
from hypothesis import assume, given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_IDENT_ALPHABET = string.ascii_letters + string.digits + "_"
_IDENTIFIERS = st.builds(
    lambda head, tail: head + tail,
    st.sampled_from(string.ascii_letters + "_"),
    st.text(alphabet=_IDENT_ALPHABET, max_size=10),
)
_VALUES = st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=12)


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_literals_captures_name_equals_value_rhs(name: str, value: str) -> None:
    """Model-based: any bare shell identifier assignment token maps its
    name to its RHS (lowercased) in the returned dict -- the exact signal
    Rule B1b's own indirection detection (``A=pip; B=install; $A $B
    foo``) depends on. Keyed by name (issue #1326 Step 8 fix), not a flat
    set of values -- see
    test_rule_b1b_ignores_unrelated_whole_command_assignments below for
    the false positive a flat set produced."""
    result = checker._assigned_literals([f"{name}={value}"])
    assert result.get(name) == value.lower()


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_literals_ignores_a_dynamic_rhs_token(name: str, value: str) -> None:
    """A token containing ``$`` is dynamic and is skipped outright before
    ``_ASSIGN_RE`` is ever consulted -- even though the token still
    textually matches the ``NAME=value`` shape."""
    result = checker._assigned_literals([f"{name}=${value}"])
    assert result == {}


@_PROPERTIES
@given(
    tokens=st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8).filter(lambda t: "=" not in t), max_size=5
    )
)
def test_assigned_literals_never_raises_on_tokens_with_no_equals_sign(tokens: list[str]) -> None:
    """Robustness: a token stream containing no ``=`` character at all
    never raises and always returns an empty dict -- ``_assigned_literals``
    runs against untrusted, attacker-shaped Bash command text."""
    assert checker._assigned_literals(tokens) == {}


@_PROPERTIES
@given(
    tool=st.sampled_from(["pnpm", "yarn", "PNPM", "Yarn"]),
    flags=st.lists(st.sampled_from(["-v", "--silent", "-s", "--no-color"]), max_size=3),
)
def test_rule_bare_install_detects_a_bare_tool_with_flags_only(tool: str, flags: list[str]) -> None:
    """Model-based: a bare ``pnpm``/``yarn`` invocation (case-insensitive)
    with nothing but flags after it installs every lockfile dependency by
    default, the same as an explicit ``install`` subcommand -- detected
    regardless of which or how many flags are present, including none at
    all (an empty ``rest`` list)."""
    segments = [[tool, *flags]]
    assert checker._rule_bare_install(segments) is not None


@_PROPERTIES
@given(tool=st.sampled_from(["pnpm", "yarn"]), subcommand=st.sampled_from(["test", "build", "run", "lint"]))
def test_rule_bare_install_allows_a_tool_with_a_positional_subcommand(tool: str, subcommand: str) -> None:
    """No false positive: a positional (non-flag) subcommand after the
    tool name means this is not a bare, everything-installing
    invocation -- ``yarn test``/``pnpm run build`` must never be
    flagged."""
    segments = [[tool, subcommand]]
    assert checker._rule_bare_install(segments) is None


@_PROPERTIES
@given(tool=st.sampled_from(["curl", "wget"]), interpreter=st.sampled_from(["sh", "bash", "zsh", "dash", "SH", "Bash"]))
def test_rule_fetch_exec_detects_download_piped_into_a_shell_interpreter(tool: str, interpreter: str) -> None:
    """Model-based: curl/wget (any casing tolerated via lowering) piped
    directly into any of the four recognized shell interpreters (any
    casing) is always detected, regardless of the download URL."""
    segments = [[tool, "https://example.invalid/install.sh"], [interpreter]]
    assert checker._rule_fetch_exec(segments) is not None


@_PROPERTIES
@given(tool=st.sampled_from(["curl", "wget"]), interpreter=st.sampled_from(["sh", "bash", "zsh", "dash"]))
def test_rule_fetch_exec_detects_download_piped_through_sudo_into_a_shell(tool: str, interpreter: str) -> None:
    """Model-based: an intervening ``sudo`` before the interpreter does
    not defeat detection -- ``interp_index`` is deliberately advanced past
    a literal ``sudo`` token before checking the interpreter name."""
    segments = [[tool, "https://example.invalid/install.sh"], ["sudo", interpreter]]
    assert checker._rule_fetch_exec(segments) is not None


@_PROPERTIES
@given(tool=st.sampled_from(["curl", "wget"]), other=st.sampled_from(["python3", "node", "cat", "tee"]))
def test_rule_fetch_exec_allows_a_download_piped_into_a_non_shell_program(tool: str, other: str) -> None:
    """No false positive: piping a download into a program that is not
    one of the four recognized shell interpreters is never flagged by
    this rule."""
    segments = [[tool, "https://example.invalid/data.json"], [other]]
    assert checker._rule_fetch_exec(segments) is None


_SHORT_FLAG_WITH_VALUE = st.tuples(st.sampled_from(["-c", "-C"]), st.sampled_from(["cfgkey=cfgval", "/tmp/some/repo"]))
_LONG_FLAG_ALONE = st.sampled_from(["--git-dir=/tmp/x/.git", "--no-pager", "--work-tree=/tmp/y"])
_GIT_GLOBAL_FLAG_GROUP = st.one_of(_SHORT_FLAG_WITH_VALUE.map(list), _LONG_FLAG_ALONE.map(lambda f: [f]))


@_PROPERTIES
@given(flag_groups=st.lists(_GIT_GLOBAL_FLAG_GROUP, max_size=3))
def test_is_git_push_segment_true_for_git_push_regardless_of_leading_global_flags(flag_groups: list[list[str]]) -> None:
    """Model-based: any sequence of git global flags between ``git`` and
    ``push`` still resolves to a detected git-push segment -- the same
    fix as the sibling ``hooks/gitapex_check_bash_safety.py`` module
    needed live for ``git -C /tmp/repo push origin HEAD``."""
    seg = ["git"]
    for group in flag_groups:
        seg.extend(group)
    seg += ["push", "origin"]
    assert checker._is_git_push_segment(seg)


@_PROPERTIES
@given(subcommand=st.sampled_from(["status", "commit", "log", "diff", "fetch", "clone"]))
def test_is_git_push_segment_false_for_a_non_push_subcommand(subcommand: str) -> None:
    """No false positive: an ordinary git subcommand that is not push,
    with no literal 'git push' substring anywhere in the segment, is
    never misdetected -- this task-agent-scoped script hard-denies any
    real git push, so a false positive here would block legitimate
    read-only git commands."""
    seg = ["git", subcommand, "--short"]
    assert not checker._is_git_push_segment(seg)


@_PROPERTIES
@given(flag=st.sampled_from(["-v", "-h", "-p", "-P"]))
def test_is_git_push_segment_true_for_boolean_short_flags_before_push(flag: str) -> None:
    """Model-based, regression pin for a real bug found live by Step 8
    independent review (issue #1326): every 2-character short flag was
    treated as consuming a following value token, which wrongly swallowed
    the ``push`` token itself as a boolean flag's "value" (``git -p push
    origin main`` was never detected -- a hard-deny bypass for this
    task-agent-scoped script). ``-v``/``-h``/``-p``/``-P`` are git's own
    boolean, no-argument short global options (confirmed against git's
    usage synopsis) -- push must still be found right after one."""
    assert checker._is_git_push_segment(["git", flag, "push", "origin"])


@_PROPERTIES
@given(flag=st.sampled_from(["-v", "-h", "-p", "-P"]), subcommand=st.sampled_from(["log", "status", "diff"]))
def test_is_git_push_segment_false_for_boolean_short_flag_before_non_push_subcommand(
    flag: str, subcommand: str
) -> None:
    """No false positive: a boolean short flag before an ordinary,
    non-push subcommand is never misdetected as git push."""
    assert not checker._is_git_push_segment(["git", flag, subcommand])


@_PROPERTIES
@given(unrelated_var=_IDENTIFIERS)
def test_rule_b1b_ignores_unrelated_whole_command_assignments(unrelated_var: str) -> None:
    """Model-based, regression pin for a real false positive found live
    by Step 8 independent review (issue #1326):
    ``TOOL=pip; VERB=install; echo done; X=$(mktemp); "$X" --help`` was
    wrongly denied, because the old whole-command flat assigned-value set
    matched *some* tool-shaped and *some* verb-shaped assignment anywhere
    in the command, regardless of whether the dynamic segment actually
    referenced either variable. Scoped now to the variable names the
    dynamic segment's own tokens actually reference."""
    name_to_value = {"TOOL": "pip", "VERB": "install"}
    seg = [f"${unrelated_var}", "--help"]
    assert not checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS)


@_PROPERTIES
@given(tool_var=_IDENTIFIERS, verb_var=_IDENTIFIERS)
def test_rule_b1b_detects_when_segment_actually_references_assigned_tool_and_verb(tool_var: str, verb_var: str) -> None:
    """True positive, still detected after the false-positive fix above:
    when the SAME segment's own dynamic tokens reference the specific
    variables assigned a watched tool and a watched verb (``A=pip;
    B=install; $A $B foo``), this must still deny."""
    if tool_var == verb_var:
        return
    name_to_value = {tool_var: "pip", verb_var: "install"}
    seg = [f"${tool_var}", f"${verb_var}", "foo"]
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS)


@_PROPERTIES
@given(unrelated_var=_IDENTIFIERS)
def test_rule_git_push_ignores_unrelated_whole_command_assignments_named_git_and_push(unrelated_var: str) -> None:
    """Model-based, regression pin for a real false positive found live
    by Step 8 independent review (issue #1326), in ``_rule_git_push``'s
    own separate inline indirection check (distinct from Rule B1b's,
    since git push is a dedicated hard-deny path in this task-scoped
    script): ``GIT=x; PUSH=y; echo done; Z=$(mktemp); "$Z" --help`` was
    wrongly denied, even though the dynamic segment's own token (``$Z``)
    references neither GIT nor PUSH."""
    name_to_value = {"GIT": "git", "PUSH": "push"}
    segments = [[f"${unrelated_var}", "--help"]]
    assert checker._rule_git_push(segments, name_to_value) is None


@_PROPERTIES
@given(git_var=_IDENTIFIERS, push_var=_IDENTIFIERS)
def test_rule_git_push_detects_when_segment_actually_references_assigned_git_and_push(
    git_var: str, push_var: str
) -> None:
    """True positive, still detected after the false-positive fix above:
    when the SAME segment's own dynamic tokens reference the specific
    variables assigned "git" and "push" (``A=git; B=push; $A $B origin
    main``), this must still hard-deny."""
    if git_var == push_var:
        return
    name_to_value = {git_var: "git", push_var: "push"}
    segments = [[f"${git_var}", f"${push_var}", "origin", "main"]]
    assert checker._rule_git_push(segments, name_to_value) is not None


@_PROPERTIES
@given(git_var=_IDENTIFIERS)
def test_rule_git_push_detects_dynamic_tool_word_with_literal_push_in_same_segment(git_var: str) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review, third round (issue #1326): ``G=git; $G push
    origin main`` was wrongly allowed. Only the tool word was dynamic --
    ``push`` was already a plain literal token in the same segment, never
    referenced by any dynamic token, so it never entered the
    indirection-lookup ``values`` set the prior fix relied on exclusively.
    A dynamic command word with a literal "push" token already present
    needs no indirection lookup at all."""
    name_to_value = {git_var: "git"}
    segments = [[f"${git_var}", "push", "origin", "main"]]
    assert checker._rule_git_push(segments, name_to_value) is not None


@_PROPERTIES
@given(unrelated_var=_IDENTIFIERS, subcommand=st.sampled_from(["test", "build", "status"]))
def test_rule_git_push_allows_dynamic_tool_word_with_an_unrelated_literal_argument(
    unrelated_var: str, subcommand: str
) -> None:
    """No false positive: a dynamic command word followed by a literal
    argument that is NOT "push" is never flagged by this rule."""
    name_to_value = {unrelated_var: "somecmd"}
    segments = [[f"${unrelated_var}", subcommand]]
    assert checker._rule_git_push(segments, name_to_value) is None


@_PROPERTIES
@given(gh_var=_IDENTIFIERS)
def test_rule_gh_any_detects_gh_hidden_behind_a_variable(gh_var: str) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review, fourth round (issue #1326): `G=gh; $G pr merge 1`
    was wrongly allowed. `_WATCHED_TOOLS` in this file never includes
    "gh" at all -- it is denied entirely via this dedicated blanket rule
    instead of the adjacent-verb table B1a/B1b serve -- so neither
    generic indirection rule ever considered `gh` a watched tool. This
    rule needed its own dedicated indirection check."""
    name_to_value = {gh_var: "gh"}
    segments = [[f"${gh_var}", "pr", "merge", "1"]]
    assert checker._rule_gh_any(segments, name_to_value) is not None


@_PROPERTIES
@given(unrelated_var=_IDENTIFIERS)
def test_rule_gh_any_allows_an_unrelated_dynamic_command_word(unrelated_var: str) -> None:
    """No false positive: a dynamic command word that does not resolve to
    "gh" is never flagged by this rule."""
    name_to_value = {unrelated_var: "somecmd"}
    segments = [[f"${unrelated_var}", "test"]]
    assert checker._rule_gh_any(segments, name_to_value) is None


@_PROPERTIES
@given(flag=st.sampled_from(["--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"]))
def test_is_git_push_segment_true_for_long_flag_separate_token_form(flag: str) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review, fourth round (issue #1326): only the fused `=`
    form of git's value-taking long global options was ever handled --
    the separate-token form (`git --git-dir /tmp/repo push origin
    master`, confirmed to actually push with real git) went undetected,
    bypassing this task-agent hard-deny rule entirely."""
    seg = ["git", flag, "/tmp/some/value", "push", "origin"]
    assert checker._is_git_push_segment(seg)


@_PROPERTIES
@given(flag=st.sampled_from(["--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"]))
def test_is_git_push_segment_true_for_long_flag_fused_equals_form(flag: str) -> None:
    """No regression: the fused `=` form these long flags already
    handled correctly continues to work after adding separate-token
    support alongside it."""
    seg = ["git", f"{flag}=/tmp/some/value", "push", "origin"]
    assert checker._is_git_push_segment(seg)


# --- Round 9: bash's own `${NAME:-default}`/`${NAME-default}`/
# `${NAME:=default}`/`${NAME=default}` parameter-expansion (issue #1326,
# found live by Step 8 independent review, ninth round). This embeds
# literal text directly in a token with NO variable assignment anywhere
# in the command at all -- `${NEVER_SET:-uv} ${NEVER_SET2:-install} foo`
# resolves (real bash) to a genuine `uv install foo`, fully bypassing
# even the most basic install-verb detection.

_DEFAULT_CLAUSE_OPERATORS = st.sampled_from([":-", "-", ":=", "="])


@_PROPERTIES
@given(name=_IDENTIFIERS, op=_DEFAULT_CLAUSE_OPERATORS, default=_VALUES)
def test_default_clause_literal_extracts_the_default_text(name: str, op: str, default: str) -> None:
    """Model-based: every one of the four default-value operator shapes
    yields the literal default text, unchanged."""
    assert checker._default_clause_literal(f"${{{name}{op}{default}}}") == default


@_PROPERTIES
@given(name=_IDENTIFIERS)
def test_default_clause_literal_none_for_a_bare_braced_reference(name: str) -> None:
    """No false positive: a bare `${NAME}` reference (no operator at all)
    is not a default-clause construct."""
    assert checker._default_clause_literal(f"${{{name}}}") is None


@_PROPERTIES
@given(tool_var=_IDENTIFIERS, verb_var=_IDENTIFIERS)
def test_rule_b1a_detects_a_default_clause_verb(tool_var: str, verb_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, ninth round (issue #1326): a watched verb
    embedded as a `${NAME:-default}` fallback in a later segment token
    (with the command word itself also dynamic) is still caught, even
    though neither variable is ever assigned."""
    seg = [f"${{{tool_var}:-pip}}", f"${{{verb_var}:-install}}", "pkg"]
    assert checker._rule_b1a_dynamic_word_same_segment_verb(seg, checker._WATCHED_VERBS)


@_PROPERTIES
@given(tool_var=_IDENTIFIERS, verb_var=_IDENTIFIERS)
def test_rule_b1b_detects_a_default_clause_tool_and_verb(tool_var: str, verb_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, ninth round (issue #1326): both the tool AND
    the verb hidden behind their own `${NAME:-default}` fallback (NO
    assignment for either variable anywhere) are still caught."""
    assume(tool_var != verb_var)
    seg = [f"${{{tool_var}:-pip}}", f"${{{verb_var}:-install}}", "pkg"]
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, {}, checker._WATCHED_VERBS)


@_PROPERTIES
@given(tool_var=_IDENTIFIERS)
def test_rule_b1a_allows_an_unrelated_default_clause_argument(tool_var: str) -> None:
    """No false positive: a dynamic command word with a default-clause
    argument that resolves to something unrelated to any watched verb
    must stay allowed."""
    seg = [f"${{{tool_var}:-cat}}", "${OTHER:-somefile.txt}"]
    assert not checker._rule_b1a_dynamic_word_same_segment_verb(seg, checker._WATCHED_VERBS)


@_PROPERTIES
@given(gh_var=_IDENTIFIERS)
def test_rule_gh_any_detects_a_default_clause_gh(gh_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, ninth round (issue #1326): `gh` hidden as a
    `${NAME:-gh}` fallback command word, with no assignment for NAME
    anywhere, is still caught."""
    segments = [[f"${{{gh_var}:-gh}}", "pr", "merge", "1"]]
    assert checker._rule_gh_any(segments, {}) is not None


@_PROPERTIES
@given(git_var=_IDENTIFIERS, push_var=_IDENTIFIERS)
def test_rule_git_push_detects_a_default_clause_git_and_push(git_var: str, push_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, ninth round (issue #1326): both `git` AND
    `push` hidden behind their own `${NAME:-default}` fallback are still
    caught."""
    assume(git_var != push_var)
    segments = [[f"${{{git_var}:-git}}", f"${{{push_var}:-push}}", "origin", "main"]]
    assert checker._rule_git_push(segments, {}) is not None

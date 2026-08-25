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
from hypothesis import given, settings
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
    """Model-based: any bare shell identifier assignment token contributes
    its RHS (lowercased) to the assigned-literal set -- the exact signal
    Rule B1b's own indirection detection (``A=pip; B=install; $A $B foo``)
    depends on."""
    result = checker._assigned_literals([f"{name}={value}"])
    assert value.lower() in result


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_literals_ignores_a_dynamic_rhs_token(name: str, value: str) -> None:
    """A token containing ``$`` is dynamic and is skipped outright before
    ``_ASSIGN_RE`` is ever consulted -- even though the token still
    textually matches the ``NAME=value`` shape."""
    result = checker._assigned_literals([f"{name}=${value}"])
    assert result == set()


@_PROPERTIES
@given(
    tokens=st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8).filter(lambda t: "=" not in t), max_size=5
    )
)
def test_assigned_literals_never_raises_on_tokens_with_no_equals_sign(tokens: list[str]) -> None:
    """Robustness: a token stream containing no ``=`` character at all
    never raises and always returns an empty set -- ``_assigned_literals``
    runs against untrusted, attacker-shaped Bash command text."""
    assert checker._assigned_literals(tokens) == set()


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

"""Regression suite for check-bash-safety.sh's own deny/warn/allow matrix.

Refs #280 (retro on PR #279), proposed gate 1: this file is the template
run named there -- the shared hook check_task_bash_safety.sh was adapted
from ("references/threat-model-and-authorization.md" documents that
lineage) had never had one either. Scope is test-only: this file asserts
today's shipped behavior, including gaps this hook does not close (e.g. it
has no `npm ci` / `pnpm install` / bare-`pnpm`/`yarn` / curl-pipe-sh / npx
coverage -- those were added to check_task_bash_safety.sh's own,
stricter, task-agent-scoped copy, not ported back here). No script logic
changes; hooks/check-bash-safety.sh is a shared dependency of multiple
skills and this task's scope is tests only.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, rather than re-deriving the regexes in Python.

Issue #1320: `uv add`/`uv remove` are declarative, PR-diff-visible
dependency changes (mutate pyproject.toml/uv.lock) and are allowed, unlike
`uv pip install`/bare `uv install`, which install into the venv with no
diff trail. `apm install`/`apm uninstall` were already unmatched by
install_re before that change (no "apm" pattern exists at all) -- pinned
here as an explicit allow regression test, not a relaxed block.

Issue #1326 (Stage 1): the predecessor implementation matched a bash
extended regex against the raw, unexpanded shell source text of
tool_input.command -- a substring scan over source text, not a check
against what bash actually executes. Live-verified bypassable by
quote-splitting, ${IFS} substitution, and several classes of
variable/array/positional-parameter indirection, all of which still
resolved to the exact denied invocation once bash actually expanded them,
and the identical techniques defeated `pip install`, `gh pr merge`, and
`git push` just as easily -- a property of the whole regex-substring
design, not one pattern. `hooks/check-bash-safety.sh` now shells out to
`hooks/gitapex_check_bash_safety.py`, a token-based classifier (shlex,
stdlib-only) -- see that module's own docstring for the full root-cause
analysis, what Stage 1 closes, and its own disclosed residual limitation
(verb-token-splitting via string-slice reconstruction or array-literal
assignment indirection, neither of which places the tool/verb name as its
own literal token anywhere in the command).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-bash-safety.sh"
REPO_ROOT = Path(__file__).parent.parent
SCAN_SCRIPT_RELATIVE = "skills/outward-artifact-preflight/scripts/gitapex_scan_provenance.py"


def run(
    command: str, tool_name: object = "Bash", extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )


def assert_denied(command: str) -> None:
    result = run(command)
    assert result.returncode == 2, (
        f"expected deny (exit 2) for {command!r}, got {result.returncode}: stderr={result.stderr!r}"
    )
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]


def assert_allowed(command: str) -> None:
    result = run(command)
    assert result.returncode == 0, (
        f"expected allow (exit 0) for {command!r}, got {result.returncode}: stderr={result.stderr!r}"
    )
    # warn() also exits 0 while emitting a systemMessage on stdout -- exit
    # code alone can't distinguish a clean allow from a regression that
    # starts warning on one of these commands, so require silence too.
    assert result.stdout == "", f"expected no warn output for {command!r}, got stdout={result.stdout!r}"
    assert result.stderr == ""


# --- Finding 1: package/plugin install verbs -------------------------------
DENIED_INSTALL_COMMANDS = [
    ("pip install requests", "pip-install"),
    ("npm install lodash", "npm-install"),
    ("npm i lodash", "npm-i"),
    ("yarn add lodash", "yarn-add"),
    ("pnpm add lodash", "pnpm-add"),
    ("go install ./...", "go-install"),
    ("brew install wget", "brew-install"),
    ("apt-get install curl", "apt-get-install"),
    ("apt install curl", "apt-install"),
    ("gem install rails", "gem-install"),
    ("cargo install ripgrep", "cargo-install"),
    ("uv pip install requests", "uv-pip-install"),
    ("uv install requests", "uv-install"),
    ("plugin install foo", "plugin-install"),
]

# --- Issue #1320: declarative package-manager commands allowed -------------
# `uv add`/`uv remove` mutate pyproject.toml/uv.lock, so a dependency change
# made this way shows up in the PR diff for review -- unlike `uv pip
# install`/bare `uv install` (still denied above), which install into the
# venv with no diff trail. `apm install`/`apm uninstall` were never matched
# by `_DENIED_ADJACENT` at all (no "apm" pattern exists); these two pin that
# already-allowed behavior as a regression test rather than relaxing an
# actual block, so a future widened denylist (e.g. a broader "plugin
# install" pattern) can't silently sweep `apm` back into deny unnoticed.
ALLOWED_DECLARATIVE_PACKAGE_COMMANDS = [
    ("uv add requests", "uv-add"),
    ("uv remove requests", "uv-remove"),
    ("apm install foo", "apm-install"),
    ("apm uninstall foo", "apm-uninstall"),
]

# --- Issue #1320 defeat-test: chaining a newly-allowed uv add/remove ahead
# of a still-denied uv pip install/uv install must NOT smuggle the denied
# verb past this gate. The token-based classifier (issue #1326) segments a
# command at shell operator boundaries (;, &&, |, ...) and checks each
# segment independently against `_DENIED_ADJACENT` -- a still-denied verb
# appearing in a LATER segment after an allowed `uv add`/`uv remove` must
# still be caught by that later segment's own check, never short-circuited
# by the earlier segment's allow.
DENIED_CHAINED_AFTER_ALLOWED_COMMANDS = [
    ("uv add safe && uv pip install malicious", "uv-add-then-pip-install-chained"),
    ("uv remove safe; uv install malicious", "uv-remove-then-install-chained"),
    ("uv add safe | uv install malicious", "uv-add-then-install-piped"),
]

# --- Findings 2 & 3: direct CLI GitHub write commands ----------------------
DENIED_GH_COMMANDS = [
    ("gh issue create --title x", "gh-issue-create"),
    ("gh issue edit 1 --title x", "gh-issue-edit"),
    ("gh issue close 1", "gh-issue-close"),
    ("gh issue comment 1 --body hi", "gh-issue-comment"),
    ("gh issue delete 42", "gh-issue-delete"),
    ("gh issue reopen 1", "gh-issue-reopen"),
    ("gh issue lock 1", "gh-issue-lock"),
    ("gh pr create --title x", "gh-pr-create"),
    ("gh pr edit 1 --title x", "gh-pr-edit"),
    ("gh pr close 1", "gh-pr-close"),
    ("gh pr merge 1", "gh-pr-merge"),
    ("gh pr merge 1 --auto", "gh-pr-merge-auto"),
    ("gh pr review 7 --approve", "gh-pr-review"),
    ("gh pr ready 1", "gh-pr-ready"),
    ("gh api repos/o/r/issues -X POST -f title=x", "gh-api-dash-x-post"),
    ("gh api repos/o/r/issues --method POST", "gh-api-method-post"),
    ("gh api repos/o/r/issues --method=POST", "gh-api-method-eq-post"),
    ("gh api repos/o/r/issues -XPOST", "gh-api-xpost-attached"),
    ("gh api graphql -f query=mutation{createissue}", "gh-api-graphql-mutation"),
    ("gh api repos/o/r/issues -f title=x", "gh-api-field-flag-implicit-write"),
]

ALLOWED_GH_COMMANDS = [
    ("gh issue view 1", "gh-issue-view"),
    ("gh issue list", "gh-issue-list"),
    ("gh pr view 1", "gh-pr-view"),
    ("gh pr list", "gh-pr-list"),
    ("gh pr diff 1", "gh-pr-diff"),
    ("gh pr checks 1", "gh-pr-checks"),
    ("gh api repos/o/r/issues", "gh-api-get-no-method"),
    ("gh api graphql -f query=query{viewer{login}}", "gh-api-graphql-query"),
    # False-positive guard for the flag-name-as-bare-variable rule added in
    # DENIED_INDIRECTION_COMMANDS above (issue #1326, fifth round): a bare
    # variable token that resolves to -X/--method must only deny when its
    # own following value resolves to a denied write method -- a read
    # method (GET/HEAD) must stay allowed, and an unresolvable variable
    # (never assigned) must not be treated as a hit either.
    ("F=-X; M=GET; gh api repos/o/r/pulls/1 $F $M", "gh-api-method-flagname-dynamic-value-read"),
    ("F=-X; gh api repos/o/r/pulls/1 $F", "gh-api-method-flagname-dynamic-no-value-token"),
    # False-positive guard for the multi-variable-concatenation resolution
    # added in DENIED_INDIRECTION_COMMANDS above (issue #1326, sixth
    # round): a concatenated value that resolves to a read method (GET)
    # must stay allowed, and a concatenation referencing an unassigned
    # variable must not be treated as a hit either.
    ('M1=GE; M2=T; gh api repos/o/r/pulls/1 -X "$M1$M2"', "gh-api-method-value-multi-var-concat-read"),
    ('M1=PO; gh api repos/o/r/pulls/1 -X "$M1$M2"', "gh-api-method-value-concat-unassigned-var"),
    # False-positive guard for the case-normalization fix added above
    # (issue #1326, seventh round): an uppercase literal fragment fused
    # with a variable that resolves to a READ method must stay allowed.
    ('M=T; gh api repos/o/r/pulls/1 -X "GE$M"', "gh-api-method-value-literal-fragment-plus-var-read-uppercase"),
    # False-positive guard for the unbraced-reference-ambiguity fix added
    # above (issue #1326, eighth round): the bounded-reference reading
    # resolving to a READ method must stay allowed.
    (
        'M=GE; gh api repos/o/r/pulls/1 -X"$M"T',
        "gh-api-method-value-unbraced-ref-followed-by-more-identifier-text-read",
    ),
    # An ordinary, totally unrelated variable adjacent to literal text
    # with no assigned-variable-name collision at all must stay allowed
    # -- the unbraced-reference-ambiguity fix must not overreach into
    # denying every dynamic token shaped like a longer identifier.
    ("REPO=owner-repo; gh api repos/$REPOissues", "gh-api-unrelated-unbraced-var-adjacent-to-literal-text"),
    # False-positive guard for the fused-flagname-plus-value fix added
    # above (issue #1326, eighth round): a fused flag-name-hidden token
    # resolving to a read method must stay allowed.
    ('F=-X; gh api repos/o/r/pulls/1 "$F"GET', "gh-api-method-fused-flagname-and-value-quote-collapsed-read"),
    # False-positive guard for the `${NAME:-default}` fix added above
    # (issue #1326, ninth round): a default-clause value resolving to a
    # read method must stay allowed.
    ("gh api repos/x/y -X${UNSET_VAR-GET}", "gh-api-method-value-default-clause-read"),
]

ALLOWED_ORDINARY_COMMANDS = [
    ("git status --short", "git-status"),
    ("git commit -m test", "git-commit"),
    ("npm run build", "npm-run-build"),
    ("npm test", "npm-test"),
    ("yarn test", "yarn-test"),
    ("pytest", "pytest"),
]

# --- Issue #1326 Stage 1: legitimate dynamic bash commands must never ------
# regress to denied, even though they contain `$`/backtick expansion --
# this is the false-positive guard the root-cause analysis's own measured
# 28% FP rate (for a "deny every dynamic command" policy) was bounding
# against. Each of these was independently confirmed allowed both before
# and after this module's own adversarial self-test iteration.
ALLOWED_DYNAMIC_COMMANDS = [
    ("git log --oneline -5 $BRANCH", "git-log-dynamic-arg"),
    ("make -j$(nproc)", "make-command-sub"),
    ("tar cf out.tar $(git ls-files)", "tar-nested-git-ls-files"),
    ("$VENV/bin/python script.py", "dynamic-interpreter-path"),
    ("export PATH=$PATH:/usr/local/bin", "export-path-append"),
    ("result=$(pip --version)", "assign-from-pip-version-readonly"),
    ("echo $HOME", "echo-dynamic-var"),
    ("cd $REPO_ROOT && pytest", "cd-dynamic-then-pytest"),
    ("for f in $(ls); do echo $f; done", "for-loop-command-sub"),
    ('git add -A && git commit -m "$(cat msg.txt)"', "git-add-commit-dynamic-message"),
    ("git add file1.txt file2.txt; result=$(date)", "git-add-then-unrelated-dynamic-assign"),
    ("gh pr list; x=$(date)", "gh-pr-list-then-unrelated-dynamic-assign"),
    ("npm run build; deploy=$(get_target)", "npm-run-build-then-unrelated-dynamic-assign"),
    ("GOFLAGS=-mod=mod go build ./...", "goflags-assign-then-go-build"),
    # False-positive guards for the `${NAME:-default}` fix added below in
    # DENIED_INDIRECTION_COMMANDS (issue #1326, ninth round): an ordinary
    # default-value fallback with no watched-tool/verb text at all, or as
    # a harmless argument to a command that doesn't invoke it, must stay
    # allowed.
    ("echo ${NEVER_SET:-hello}", "default-clause-unrelated-text"),
    ("${NEVER_SET:-cat} file.txt", "default-clause-unwatched-tool"),
    ("echo ${NEVER_SET:-uv}", "default-clause-watched-tool-name-as-echo-argument"),
    # False-positive guards for the `${!NAME}` indirect-reference fix
    # added above in DENIED_INDIRECTION_COMMANDS (issue #1326, tenth
    # round): an indirect reference resolving to something unrelated must
    # stay allowed, and the two-level lookup must not itself misfire when
    # the first level is unresolvable.
    ("REF=R; R=cat; ${!REF} file.txt", "indirect-ref-unwatched-tool"),
    ("REF=R; R=hello; echo ${!REF}", "indirect-ref-unrelated-text-as-echo-argument"),
    ("echo ${!NEVER_ASSIGNED}", "indirect-ref-first-level-unresolved"),
    # False-positive guard for the eleventh-round fused-indirect-ref fix:
    # a fused reconstruction resolving to something unrelated (not a
    # watched tool/verb) must stay allowed.
    ("REF=R; R=at; c${!REF} file.txt", "fused-indirect-ref-unwatched-tool"),
    # False-positive guard for the twelfth-round fused-flagname fix: a
    # `gh api` flag name fused with a literal prefix that resolves to
    # something other than a watched flag must stay allowed.
    ("X=x; gh api repos/o/r/issues --$X", "fused-flagname-unwatched-flag"),
    # False-positive guards for the fourteenth-round command-substitution
    # fixes: an ordinary, harmless `$(...)` used as plain argument text
    # (not the command word, and embedding no denied command of its own)
    # must stay allowed -- the root-cause analysis's own measured 28% FP
    # rate is exactly what an over-broad "any unresolvable $(...) denies"
    # policy would reproduce.
    ('echo "today is $(date)"', "command-substitution-as-harmless-echo-argument"),
    ("x=$(date +%s); echo $x", "assignment-from-harmless-command-substitution"),
    ('git commit -m "fixed $(date)"', "command-substitution-in-commit-message-argument"),
    ("gh api repos/o/r/pulls/1 -XGET", "gh-api-literal-get-stays-allowed"),
]

# --- Known, disclosed, unresolved regex/token-gate bypasses ----------------
# This script shares the same cmd_boundary/whitespace-anchored regex
# construction that skills/executing-a-branch-plan/scripts/
# check_task_bash_safety.sh was adapted from -- its own KNOWN_BYPASS_COMMANDS
# (see the sibling test file) pins these identical 4 cases as unresolved
# there; this script is equally bypassed by them today (verified directly:
# all 4 return exit 0/unblocked against this script too), but neither this
# script's own header comment nor references/threat-model-and-authorization.md
# discloses that ceiling for THIS file specifically -- only for the sibling.
# These tests pin *current* (bypassed) behavior, same as the sibling file's:
# not a "should be fixed" assertion. If one of these ever starts returning
# exit 2, the gap closed -- update this test (and consider whether the
# disclosure convention now needs to name this script too).
KNOWN_BYPASS_COMMANDS = [
    (
        'cmd=uvinstall; eval "${cmd:0:2} ${cmd:2}" foo',
        "string-slice-reconstruction-uv-install",
    ),
    (
        'A=(uv); V=(install); "${A[@]}" "${V[@]}" foo',
        "array-literal-assignment-indirection",
    ),
    (
        # Found live by Step 8 independent review, fourth round (issue
        # #1326): the `gh api graphql` "mutation" keyword check is a raw
        # substring scan over the whole command text (see
        # _rule_gh_api_write's own docstring) -- sound against a literal
        # "mutation" keyword, but not against one reconstructed at
        # runtime by concatenating two separately-assigned variables.
        # Soundly closing this requires resolving nested `${NAME}`
        # references through recursive variable substitution -- the same
        # unbounded-reconstruction problem issue #1326 itself already
        # scopes out of Stage 1 ("verb reconstruction that never places
        # the tool/verb name as its own literal token anywhere in the
        # command"), manifesting here for the mutation keyword instead of
        # a tool/verb token. Deliberately not attempted in Stage 1.
        'A=muta; B=tion; Q="${A}${B} { x }"; gh api graphql -f query="$Q"',
        "graphql-mutation-keyword-variable-concatenation",
    ),
]


@pytest.mark.parametrize("command,case_id", DENIED_INSTALL_COMMANDS, ids=[c[1] for c in DENIED_INSTALL_COMMANDS])
def test_denied_install(command: str, case_id: str) -> None:
    assert_denied(command)


@pytest.mark.parametrize(
    "command,case_id",
    ALLOWED_DECLARATIVE_PACKAGE_COMMANDS,
    ids=[c[1] for c in ALLOWED_DECLARATIVE_PACKAGE_COMMANDS],
)
def test_allowed_declarative_package_commands(command: str, case_id: str) -> None:
    assert_allowed(command)


@pytest.mark.parametrize("command,case_id", DENIED_GH_COMMANDS, ids=[c[1] for c in DENIED_GH_COMMANDS])
def test_denied_gh(command: str, case_id: str) -> None:
    assert_denied(command)


@pytest.mark.parametrize("command,case_id", ALLOWED_GH_COMMANDS, ids=[c[1] for c in ALLOWED_GH_COMMANDS])
def test_allowed_gh(command: str, case_id: str) -> None:
    assert_allowed(command)


@pytest.mark.parametrize("command,case_id", ALLOWED_ORDINARY_COMMANDS, ids=[c[1] for c in ALLOWED_ORDINARY_COMMANDS])
def test_allowed_ordinary(command: str, case_id: str) -> None:
    assert_allowed(command)


@pytest.mark.parametrize("command,case_id", ALLOWED_DYNAMIC_COMMANDS, ids=[c[1] for c in ALLOWED_DYNAMIC_COMMANDS])
def test_allowed_dynamic_false_positive_guard(command: str, case_id: str) -> None:
    assert_allowed(command)


@pytest.mark.parametrize(
    "command,case_id",
    DENIED_CHAINED_AFTER_ALLOWED_COMMANDS,
    ids=[c[1] for c in DENIED_CHAINED_AFTER_ALLOWED_COMMANDS],
)
def test_denied_chained_after_allowed(command: str, case_id: str) -> None:
    assert_denied(command)


@pytest.mark.parametrize("command,case_id", KNOWN_BYPASS_COMMANDS, ids=[c[1] for c in KNOWN_BYPASS_COMMANDS])
def test_known_bypass_still_unblocked(command: str, case_id: str) -> None:
    result = run(command)
    assert result.returncode == 0, (
        f"documented bypass {case_id!r} ({command!r}) is now blocked (exit {result.returncode}); "
        "if this is an intentional fix, update this test and gitapex_check_bash_safety.py's own "
        "module docstring together"
    )


# --- Issue #1326 Stage 1: the bypass techniques this module actually -------
# closes -- pinned as DENIED, the inverse of the KNOWN_BYPASS_COMMANDS
# above. Each was live-confirmed, before this module existed, to bypass
# the predecessor's raw-regex scan while still resolving (via a stand-in
# `uv` binary echoing its own argv) to the real denied invocation.
# git-push's own obfuscated forms are deliberately NOT here -- git push is
# warn, not deny, even in its plain literal form (Finding 4 below), so an
# obfuscated one stays on that same warn path; see
# OBFUSCATED_GIT_PUSH_WARN_PATH_COMMANDS further down.
DENIED_INDIRECTION_COMMANDS = [
    ("A=uv; B=install; $A $B foo", "var-split-tool-and-verb"),
    ("x=install; uv $x foo", "var-split-verb-only"),
    ("T=uv; $T install foo", "var-split-tool-only"),
    ('V="in""stall"; uv $V foo', "var-concat-verb-pieces"),
    ('set -- install foo; uv "$@"', "positional-params-indirection"),
    ('uv $(printf "\\151\\156\\163\\164\\141\\154\\154") foo', "printf-octal-verb-reconstruction"),
    ('u""v install foo', "quote-split-uv"),
    ('uv in""stall foo', "quote-split-install-verb"),
    ("u\\v install foo", "backslash-escape-uv"),
    ("uv${IFS}install foo", "ifs-uv-install"),
    ("pip${IFS}install foo", "ifs-substitution-pip-install"),
    (r"p\ip install foo", "backslash-escape-pip"),
    ("A=gh;B=pr;C=merge; $A $B $C 1", "var-split-gh-pr-merge"),
    ('echo "uv install foo" | bash', "echo-literal-piped-to-bash"),
    ('$(echo "uv install foo")', "command-sub-wrapped-full-text"),
    # Found live by Step 8 independent review, fifth round (issue #1326):
    # not just the -X/--method or -f/--field VALUE hidden behind a
    # variable (already covered by the gh-api-* cases in DENIED_GH_COMMANDS
    # above), but the flag NAME itself as a bare variable token -- every
    # prior fix assumed the flag token carried a literal "-x"/"--method"/
    # "-f"/"--field" text prefix somewhere in itself, which a pure `$F`
    # token never has.
    ("F=-X; M=POST; gh api repos/o/r/pulls/1/merge $F $M", "gh-api-method-flagname-and-value-both-dynamic"),
    ("F=-X; gh api repos/o/r/pulls/1/merge $F POST", "gh-api-method-flagname-dynamic-value-literal"),
    ("FF=--field; gh api repos/o/r/pulls/1 $FF name=value", "gh-api-field-flagname-dynamic"),
    # Found live by Step 8 independent review, sixth round (issue #1326):
    # a write-method value split across multiple concatenated variables
    # (bash concatenates adjacent `$NAME` references with no separator)
    # was never recognized, because the prior fix checked each referenced
    # variable's resolved value separately -- neither "po" nor "st" alone
    # is a write method, but bash resolves `"$M1$M2"` to the single word
    # "POST".
    ('M1=PO; M2=ST; gh api repos/o/r/pulls/1/merge -X "$M1$M2"', "gh-api-method-value-multi-var-concat"),
    (
        'F=-X; M1=PO; M2=ST; gh api repos/o/r/pulls/1/merge $F "$M1$M2"',
        "gh-api-method-flagname-and-value-concat-both-dynamic",
    ),
    # Found live by Step 8 independent review, seventh round (issue
    # #1326): `_substitute_var_refs` preserves a token's literal text
    # exactly as typed -- only the substituted variable values are
    # already-lowercased -- so a literal fragment fused with a variable
    # in the SAME token (`-X "PO$M"` with `M=ST`) reconstructed to
    # "POst", which the write-method comparison (case-sensitive
    # `.startswith`) never matched. Every existing concatenation test
    # used a whole-variable-per-fragment split (`M1=PO; M2=ST`), which
    # happens to already be all-lowercase after `_assigned_literals`'s
    # own lowercasing, so this literal-fragment gap went unexercised.
    ('M=ST; gh api repos/o/r/pulls/1/merge -X "PO$M"', "gh-api-method-value-literal-fragment-plus-var-uppercase"),
    ("M=ST; gh api repos/o/r/pulls/1/merge -XPO$M", "gh-api-method-value-fused-literal-fragment-plus-var-uppercase"),
    (
        "M=ST; gh api repos/o/r/pulls/1/merge --method=PO$M",
        "gh-api-method-value-method-eq-literal-fragment-plus-var-uppercase",
    ),
    (
        'F=-X; M=ST; gh api repos/o/r/pulls/1/merge $F "PO$M"',
        "gh-api-method-flagname-dynamic-value-literal-fragment-plus-var-uppercase",
    ),
    # Found live by Step 8 independent review, eighth round (issue
    # #1326): shlex's own quote removal discards WHICH characters were
    # originally inside quotes. `-X"$M"ST` (a quoted, bounded reference
    # to `M` followed by literal `ST`) and `-X$MST` (a bare, unquoted
    # reference to a variable literally named `MST`) both dequote to the
    # identical raw token text `-X$MST` -- there is no way to recover,
    # from the token alone, which reading bash actually used. Real bash
    # (confirmed via `bash -c` argv expansion) resolves `-X"$M"ST` with
    # `M=PO` to a real `-XPOST` write.
    (
        'M=PO; gh api repos/o/r/pulls/1/merge -X"$M"ST',
        "gh-api-method-value-unbraced-ref-followed-by-more-identifier-text",
    ),
    (
        'M=PO; gh api repos/o/r/pulls/1/merge --method="$M"ST',
        "gh-api-method-value-method-eq-unbraced-ref-followed-by-more-identifier-text",
    ),
    (
        'F=-X; M=PO; gh api repos/o/r/pulls/1/merge $F "$M"ST',
        "gh-api-method-flagname-dynamic-value-unbraced-ref-followed-by-more-identifier-text",
    ),
    # Found live by Step 8 independent review, eighth round (issue
    # #1326), immediately after the plain quote-boundary-ambiguity case
    # above: the SAME shlex quote-removal ambiguity applies when the flag
    # NAME itself (not just its value) is hidden behind a variable fused
    # directly with its own value in the SAME token. `F=-X; gh api ...
    # "$F"POST` dequotes to the single token `$FPOST`; real bash resolves
    # it to a real `-XPOST` write.
    ('F=-X; gh api repos/o/r/pulls/1/merge "$F"POST', "gh-api-method-fused-flagname-and-value-quote-collapsed"),
    # Same class for the field flag: `FF=-f; gh api ... "$FF"name=value`
    # dequotes to `$FFname=value`; real bash resolves it to a real
    # `-fname=value` field write.
    ('FF=-f; gh api repos/o/r/pulls/1 "$FF"name=value', "gh-api-field-fused-flagname-and-value-quote-collapsed"),
    # Found live by Step 8 independent review, ninth round (issue #1326):
    # bash's own `${NAME:-default}`/`${NAME-default}` parameter-expansion
    # embeds literal text directly in a token with NO variable assignment
    # anywhere in the command at all. Real bash resolves
    # `-X${TOTALLY_NEVER_MENTIONED-POST}` to a real `-XPOST` write.
    (
        "gh api repos/x/y/merge -X${TOTALLY_NEVER_MENTIONED-POST}",
        "gh-api-method-value-default-clause-fused",
    ),
    (
        "gh api repos/x/y/merge --method=${UNSET_VAR:-POST}",
        "gh-api-method-value-method-eq-default-clause-fused",
    ),
    (
        'gh api repos/x/y/merge -X "${UNSET_VAR:-POST}"',
        "gh-api-method-value-default-clause-separate-token",
    ),
    # Same mechanism, but defeating the much more basic install-verb
    # detection (not gh-api-specific) with zero variable assignment at
    # all -- real bash resolves this to a genuine `uv install foo`.
    ("${NEVER_SET:-uv} install foo", "default-clause-tool-only"),
    ("${NEVER_SET:-uv} ${NEVER_SET2:-install} foo", "default-clause-tool-and-verb-both"),
    ("uv ${NEVER_SET:-install} foo", "default-clause-verb-only"),
    (
        "${NEVER_SET:-gh} ${NEVER_SET2:-pr} ${NEVER_SET3:-merge} 1",
        "default-clause-gh-pr-merge-all-hidden",
    ),
    # Found live by Step 8 independent review, tenth round (issue #1326):
    # bash's own `${!NAME}` indirect-reference syntax (a TWO-LEVEL lookup
    # -- NAME's own value names a second variable, whose value is the
    # final result) contributed NOTHING to any rule's referenced-name/
    # value collection before this round -- confirmed live via real bash
    # argv expansion that each of these resolves to a genuine denied
    # invocation.
    (
        "TOOLREF=T; T=uv; VERBREF=V; V=install; ${!TOOLREF} ${!VERBREF} foo",
        "indirect-ref-tool-and-verb-both-hidden",
    ),
    ("GREF=G; G=gh; ${!GREF} pr merge 1", "indirect-ref-gh-hidden"),
    (
        "MREF=M; M=POST; gh api repos/x/y/merge -X${!MREF}",
        "gh-api-method-value-indirect-ref",
    ),
    # Found live by Step 8 independent review, eleventh round (issue
    # #1326): every one of the narrow, whole-token-anchored resolvers
    # (default-clause extraction, `${!NAME}` indirect reference) requires
    # the ENTIRE token to be exactly one recognized construct -- blind to
    # that same construct FUSED with literal text in the same token.
    # Real bash resolves each of these to a genuine denied invocation.
    (
        "T=uv; SUFNAME=SUFVAL; SUFVAL=stall; $T in${!SUFNAME} foo",
        "fused-indirect-ref-verb-with-literal-prefix",
    ),
    (
        "HSUF=HVAL; HVAL=h; g${!HSUF} pr merge 1",
        "fused-indirect-ref-gh-with-literal-prefix",
    ),
    (
        "HSUF=HVAL; HVAL=h; MSUF=MVAL; MVAL=erge; g${!HSUF} pr m${!MSUF} 1",
        "fused-indirect-ref-tool-and-verb-both-with-literal-prefix",
    ),
    (
        "T=uv; $T in${UNSETVAR:-stall} foo",
        "fused-default-clause-verb-with-literal-prefix",
    ),
    # Found live by Step 8 independent review, twelfth round (issue
    # #1326): round eleven's own claim that "a flag name is never fused
    # with other text the way a value can be" was wrong -- a `gh api`
    # flag NAME reconstructed by fusing a literal `--` prefix with a
    # variable reference in the SAME token was invisible to the
    # whole-token-only flag-NAME resolver. Real bash resolves each of
    # these to a genuine denied write.
    (
        "M=method; gh api repos/o/r/issues --$M POST",
        "fused-flagname-method-with-literal-prefix",
    ),
    (
        "FF=field; gh api repos/o/r/issues --$FF name=value",
        "fused-flagname-field-with-literal-prefix",
    ),
    # Found live by Step 8 independent review, fourteenth round (issue
    # #1326): a general literal-token-adjacency bypass -- `segment_
    # tokens` used to split a bare command word from whatever followed a
    # `(`, so a tool/verb pair hidden behind a `$(...)` command-
    # substitution wrapper evaded every literal-adjacency and B-rule
    # indirection check, confirmed live via a real bash proxy that each
    # substitution genuinely resolves to the plain literal invocation.
    ("$(echo pip) install foo", "command-substitution-wrapped-pip-install"),
    ("$(echo uv) install foo", "command-substitution-wrapped-uv-install"),
    ("$(echo gh) pr merge 1", "command-substitution-wrapped-gh-pr-merge"),
    # Found live by Step 8 independent review, fourteenth round (issue
    # #1326), the gh-api flag-value counterpart: a `-X`/`--method` or
    # `-f`/`--field` flag whose value is itself a `$(...)` command
    # substitution resolving to a write method was invisible to the
    # write-method literal-prefix comparison, since the folded
    # substitution's own reconstructed text never itself starts with the
    # write-method text.
    ("gh api repos/o/r/pulls/1/merge -X$(echo POST)", "gh-api-method-value-command-substitution-fused"),
    ("gh api repos/o/r/pulls/1/merge -X $(echo POST)", "gh-api-method-value-command-substitution-separate"),
    ("gh api repos/o/r/pulls/1/merge $(echo -X) POST", "gh-api-method-flagname-command-substitution"),
]


@pytest.mark.parametrize(
    "command,case_id", DENIED_INDIRECTION_COMMANDS, ids=[c[1] for c in DENIED_INDIRECTION_COMMANDS]
)
def test_denied_indirection(command: str, case_id: str) -> None:
    assert_denied(command)


# --- Issue #1326 Stage 1: obfuscated git push is treated as git push, ------
# warn (not deny) not a hard deny, and the provenance scan still runs
# against it -- consistent with a literal `git push`'s own existing
# warn-not-deny treatment (Finding 4 below), not a new asymmetry.
OBFUSCATED_GIT_PUSH_WARN_PATH_COMMANDS = [
    ("git${IFS}push origin HEAD", "ifs-git-push-still-warn-path"),
    ('gi""t push origin HEAD', "quote-split-git-push-still-warn-path"),
    ("P=push; git $P origin main", "var-split-git-push-verb-still-warn-path"),
    ("A=git;B=push; $A $B origin main", "var-split-git-push-both-still-warn-path"),
    # Found live by Step 8 independent review, tenth round (issue #1326):
    # same `${!NAME}` indirect-reference class as DENIED_INDIRECTION_
    # COMMANDS above, for git push specifically -- real bash resolves this
    # to a genuine `git push origin main`.
    (
        "GITREF=G; G=git; PUSHREF=P; P=push; ${!GITREF} ${!PUSHREF} origin main",
        "indirect-ref-git-push-both-hidden-still-warn-path",
    ),
]


@pytest.mark.parametrize(
    "command,case_id",
    OBFUSCATED_GIT_PUSH_WARN_PATH_COMMANDS,
    ids=[c[1] for c in OBFUSCATED_GIT_PUSH_WARN_PATH_COMMANDS],
)
def test_obfuscated_git_push_goes_through_warn_path_not_denied(command: str, case_id: str) -> None:
    # Not assert_allowed(): with no real provenance-flagged commit in this
    # test's own git history, the scan should stay silent, but this
    # specifically asserts "not denied" (exit != 2) is the property that
    # matters -- assert_allowed's stricter silence check is exercised by
    # test_allowed_ordinary's own plain `git status`/`git commit` cases.
    result = run(command)
    assert result.returncode != 2, f"expected obfuscated git push to warn, not deny; got exit {result.returncode}"


def test_non_bash_tool_name_is_ignored() -> None:
    result = run("gh pr merge 1", tool_name="Write")
    assert result.returncode == 0


def test_empty_command_is_allowed() -> None:
    assert_allowed("")


# ---------------------------------------------------------------------------
# Issue #1208: fail closed, not open, when jq is missing or the payload is
# malformed. Ported guard prologue, same one hooks/check-pr-issue-acm-
# disclosure.sh and hooks/check-pr-title-convention.sh already carried.
# ---------------------------------------------------------------------------


def _no_jq_path(tmp_path: Path) -> str:
    """A PATH directory holding every tool this script needs except jq, so
    `command -v jq` genuinely fails the way it would in an environment
    without jq installed -- rather than mocking that condition."""
    bin_dir = tmp_path / "no-jq-path"
    bin_dir.mkdir()
    for tool in ("bash", "cat", "tr", "grep", "sed", "git", "python3", "dirname"):
        real = shutil.which(tool)
        if real:
            (bin_dir / tool).symlink_to(real)
    return str(bin_dir)


def _no_python3_path(tmp_path: Path) -> str:
    """A PATH directory holding every tool this script needs except
    python3, so the classifier invocation genuinely fails to launch the
    way it would in an environment missing python3 -- issue #1326's own
    new dependency, mirroring _no_jq_path's existing approach for jq."""
    bin_dir = tmp_path / "no-python3-path"
    bin_dir.mkdir()
    for tool in ("bash", "cat", "tr", "grep", "sed", "git", "jq", "dirname"):
        real = shutil.which(tool)
        if real:
            (bin_dir / tool).symlink_to(real)
    return str(bin_dir)


def test_denied_when_jq_missing(tmp_path: Path) -> None:
    """Live-reproduced before this fix: with jq absent, the very first jq
    call (extracting tool_name) crashed under `set -e` with exit 127
    ("command not found") -- before deny() was even defined, and non-
    blocking per Claude Code's PreToolUse contract, so an arbitrary Bash
    command (including `gh pr merge`) would have proceeded unchecked. Must
    now deny (exit 2) instead."""
    result = run("gh pr merge 1", extra_env={"PATH": _no_jq_path(tmp_path)})
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "jq is not available" in payload["systemMessage"]


def test_denied_when_python3_missing(tmp_path: Path) -> None:
    """Issue #1326: the classifier invocation itself now depends on
    python3 (in addition to jq, still checked first, above). A broken
    environment missing python3 must fail closed the same way a missing
    jq does, not silently let the Bash command through unchecked."""
    result = run("gh pr merge 1", extra_env={"PATH": _no_python3_path(tmp_path)})
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_on_malformed_json_stdin() -> None:
    """Live-reproduced before this fix: jq's own parse-error exit (5)
    propagated past deny() under `set -e` -- non-blocking per Claude Code's
    PreToolUse contract. Must now deny (exit 2) instead."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not valid json{{{",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "tool_input",
    [["not", "an", "object"], "text", False, True, 0],
    ids=["array", "string", "false", "true", "zero"],
)
def test_denied_when_tool_input_is_not_an_object(tool_input: object) -> None:
    """A well-formed top-level payload whose tool_input is itself a
    non-object would otherwise crash the `.tool_input.command` access with
    jq's own "Cannot index" error. Must deny.

    `false` is the case that actually escaped the original guard: found by
    code review (PR #1213) after the array/string cases above already
    passed -- jq's `//` operator treats JSON `false` the same as `null`
    (both are falsy), so `(.tool_input // {}) | type == "object"` wrongly
    accepted it, and the crash happened one line later, past deny(). Now
    validated inside gitapex_check_bash_safety.py's own main() via an
    explicit isinstance(..., dict) check (never a falsy-or shortcut), the
    same discipline ported to Python."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": tool_input})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2) for tool_input={tool_input!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allowed_when_tool_input_is_absent_or_null() -> None:
    """jq indexes `null`/a missing key as `null`, not a runtime error, so
    these fall through the shape guard to the hook's own downstream logic
    (an empty `command` here, which is itself allowed) rather than being
    wrongly caught by it -- unlike the non-object shapes above."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    for payload in (
        json.dumps({"tool_name": "Bash"}),
        json.dumps({"tool_name": "Bash", "tool_input": None}),
    ):
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"payload={payload!r}: expected allow, got {result.returncode}"
        assert result.stdout == ""
        assert result.stderr == ""


@pytest.mark.parametrize("tool_name", [["Bash"], {"x": 1}, 5, True], ids=["array", "object", "number", "bool"])
def test_denied_when_tool_name_is_not_a_string(tool_name: object) -> None:
    """Found by code review (PR #1213): jq -r never errors on a non-string
    `.tool_name` -- it pretty-prints the JSON form across multiple lines
    instead, which then never equals the plain "Bash" string the matcher
    re-check compares against, silently falling through as "not our tool"
    (exit 0) instead of failing closed. Live-confirmed before this guard
    existed: an array-wrapped tool_name let a `gh pr merge` command
    straight through. Must now deny."""
    result = run("gh pr merge 1", tool_name=tool_name)
    assert result.returncode == 2, f"expected deny (exit 2) for tool_name={tool_name!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "command",
    [["gh", "pr", "merge", "1"], {"argv": ["gh", "pr", "merge", "1"]}, 5, True],
    ids=["array", "object", "number", "bool"],
)
def test_denied_when_tool_input_command_is_not_a_string(command: object) -> None:
    """jq -r never errors on a non-string `.tool_input.command` -- for an
    array/object it pretty-prints the JSON form across multiple lines,
    which would split a dangerous substring across JSON punctuation
    (quotes, commas, brackets) and break a whitespace-anchored regex,
    silently letting a genuinely dangerous command through instead of
    failing closed. Now validated in gitapex_check_bash_safety.py's own
    main() via isinstance(command, str)."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2) for command={command!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_on_valid_json_non_object_stdin() -> None:
    """Valid JSON that isn't an object at the top level (e.g. a bare array)
    would otherwise crash the first field-extraction jq call the same way.
    Must deny."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="[]",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------------
# Finding 4: git push gated (warn, not deny) on gitapex_scan_provenance.py
# ---------------------------------------------------------------------------


def _init_diverged_repo(repo_dir: Path, *, feature_commit_messages: list[str]) -> None:
    """Build a repo with a `main` base commit, then check out a `feature`
    branch (left as HEAD) carrying one commit per message.

    Committing onto a *separate* branch -- rather than straight onto
    `main`, as an earlier version of this fixture did -- matters: with no
    upstream set, hooks/check-bash-safety.sh falls back to `merge-base
    <candidate-ref> HEAD` against origin/HEAD, origin/main, origin/master,
    main, master in turn. If HEAD *is* `main` (the earlier fixture), that
    merge-base is HEAD itself, the scan range collapses to empty, and the
    script silently falls through to its tip-commit-only fallback -- the
    exact old behavior the merge-base range scan was added to fix, and a
    regression back to it would pass this fixture undetected. Diverging
    onto `feature` gives `main` a distinct, earlier tip, so the merge-base
    range genuinely spans every `feature_commit_messages` commit, not just
    HEAD's own tip.
    """

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=str(repo_dir),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            # Isolate from the host/CI runner's own global or system git
            # config (e.g. commit.gpgsign=true with no reachable signing
            # key) so this fixture can't hang or fail for reasons unrelated
            # to check-bash-safety.sh's own behavior.
            env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
        )

    repo_dir.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    git("symbolic-ref", "HEAD", "refs/heads/main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo_dir / "a.txt").write_text("base\n")
    git("add", "a.txt")
    git("commit", "-q", "-m", "base commit")
    git("checkout", "-q", "-b", "feature")
    for i, message in enumerate(feature_commit_messages):
        (repo_dir / "a.txt").write_text(f"change {i}\n")
        git("add", "a.txt")
        git("commit", "-q", "-m", message)


def test_git_push_denied_when_scan_script_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    result = run("git push origin HEAD", extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)})
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gitapex_scan_provenance.py" in payload["systemMessage"]


def _fake_session_url() -> str:
    # Assembled at runtime rather than written as one contiguous literal:
    # gitapex_scan_provenance.py's own "anthropic session domain" pattern would
    # otherwise match this fixture in this very file's diff, making the
    # production pre-push hook warn on this test file itself whenever this
    # commit is part of an outgoing push.
    return "https://" + "claude.ai" + "/x/session_" + "abc123"


def _project_with_scan_script(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    scan_dir = project_dir / "skills" / "outward-artifact-preflight" / "scripts"
    scan_dir.mkdir(parents=True)
    (scan_dir / "gitapex_scan_provenance.py").write_text((REPO_ROOT / SCAN_SCRIPT_RELATIVE).read_text())
    return project_dir


def test_git_push_warns_when_scan_flags_a_hit(tmp_path: Path) -> None:
    project_dir = _project_with_scan_script(tmp_path)
    # The marker sits in the *first* feature commit, with a clean commit on
    # top as HEAD -- so this only passes if the merge-base range scan (both
    # feature commits) runs, not the tip-only fallback (which would see
    # only the clean tip and miss it). See _init_diverged_repo's docstring.
    _init_diverged_repo(
        project_dir,
        feature_commit_messages=[
            f"Add feature\n\nSee {_fake_session_url()} for context.",
            "Fix typo",
        ],
    )
    result = run(
        "git push origin HEAD",
        extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)},
    )
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert "flagged the outgoing push for review" in payload["systemMessage"]


def _project_with_huge_warning_scan_script(tmp_path: Path, *, size: int = 3_000_000) -> Path:
    """A project dir whose scan script is a stand-in, not the real
    gitapex_scan_provenance.py: it always exits 1 with `size` bytes of
    output, to exercise warn()'s own robustness against a large message in
    isolation from the real scanner's detection logic (covered by that
    script's own test suite elsewhere)."""
    project_dir = tmp_path / "project"
    scan_dir = project_dir / "skills" / "outward-artifact-preflight" / "scripts"
    scan_dir.mkdir(parents=True)
    (scan_dir / "gitapex_scan_provenance.py").write_text(f"import sys\nsys.stdout.write('A' * {size})\nsys.exit(1)\n")
    return project_dir


def test_git_push_warn_survives_a_huge_scan_message(tmp_path: Path) -> None:
    """Found by code review (PR #1213): warn()'s own pre-fix form (`jq -n
    --arg`) crashed with exit 126 ("Argument list too long") on a
    message this large -- live-confirmed before the fix, via the same
    construction used here. Under `set -euo pipefail` that crash would
    abort the whole script before `exit 0`; the push still proceeds
    either way (any non-2 exit is non-blocking per Claude Code's
    PreToolUse contract), but the warning itself would be silently lost
    instead of reaching the operator. Must now exit 0 with the full
    message intact."""
    project_dir = _project_with_huge_warning_scan_script(tmp_path)
    _init_diverged_repo(project_dir, feature_commit_messages=["Fix bug in parser"])
    result = run(
        "git push origin HEAD",
        extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)},
    )
    assert result.returncode == 0, f"expected allow (exit 0), got {result.returncode}: stderr={result.stderr[:500]!r}"
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert "flagged the outgoing push for review" in payload["systemMessage"]
    assert len(payload["systemMessage"]) > 3_000_000


def test_git_push_silent_when_scan_finds_nothing(tmp_path: Path) -> None:
    project_dir = _project_with_scan_script(tmp_path)
    _init_diverged_repo(project_dir, feature_commit_messages=["Fix bug in parser"])
    result = run(
        "git push origin HEAD",
        extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

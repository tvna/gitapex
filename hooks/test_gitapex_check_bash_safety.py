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
    command: str,
    tool_name: object = "Bash",
    extra_env: dict[str, str] | None = None,
    payload_cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """PAYLOAD_CWD (issue #1375) sets the PreToolUse payload's own `.cwd`
    field -- the Bash tool call's own working directory, as Claude Code's
    real hook JSON carries it -- kept distinct from this `subprocess.run`
    call's own `cwd=` below (always REPO_ROOT, so the script can find its
    own classifier companion file via `BASH_SOURCE`), the same split
    hooks/check-bash-safety.sh's own new git checkout/restore wrapper step
    relies on: it reads `.cwd` from the payload for its live `git diff`
    check, never `${CLAUDE_PROJECT_DIR:-$(pwd)}`."""
    tool_input: dict[str, object] = {"command": command}
    payload_obj: dict[str, object] = {"tool_name": tool_name, "tool_input": tool_input}
    if payload_cwd is not None:
        payload_obj["cwd"] = payload_cwd
    payload = json.dumps(payload_obj)
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
    # False-positive guard for the round-26 `read`/array-element/
    # `printf -v` reassignment-poisoning fix (issue #1375): `read`-ing (or
    # array-assigning, or `printf -v`-ing) into a name never referenced by
    # this call at all -- a totally unrelated name -- must not poison this
    # unrelated `gh api` read call.
    ('read UNRELATED <<< "x"; gh api repos/o/r/issues', "gh-api-get-unrelated-name-read-into"),
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
    # False-positive guards for the fifteenth-round array-literal-folding
    # fix, re-pinned end to end after the sixteenth round's own
    # conditional-fold redesign (issue #1326): an array literal whose own
    # elements are harmless -- dynamic (a command substitution's output)
    # or plain literal text matching no denied pattern -- must stay
    # allowed either way.
    ("declare -a arr=($(seq 1 5))", "array-literal-dynamic-element-stays-allowed"),
    ("files=($(ls *.txt))", "array-literal-leading-dynamic-element-stays-allowed"),
    ("arr=(a b c)", "array-literal-leading-harmless-literal-stays-allowed"),
    ("declare -a arr=(a b c)", "array-literal-non-leading-harmless-literal-stays-allowed"),
    # False-positive guard for the twenty-ninth-round `$IFS`-reassignment
    # fix (issue #1326): the twenty-eighth round's own blanket "IFS
    # reassigned anywhere -> always treat as vanishing" rule wrongly
    # stripped a REAL, non-vanishing leading reference as a decoy purely
    # because `$IFS` was reassigned elsewhere in the command, wrongly
    # denying this benign command. Confirmed live via real bash that
    # `IFS=x; REAL=foo; $REAL uv $VERB` real-expands to `foo uv`, never
    # touching the watched `uv` tool in dynamic-verb position.
    ("IFS=x; REAL=foo; $REAL uv $VERB", "dynamic-wrapper-stays-allowed-despite-unrelated-ifs-reassignment"),
    # False-positive guard for the round-26 `read`/array-element/
    # `printf -v` reassignment-poisoning fix (issue #1375): the new
    # poisoning check in `_segment_loop_hit` is scoped to segments whose
    # OWN command word (`seg[0]`) is itself dynamic -- an unrelated `read`
    # elsewhere in the command must stay allowed.
    ('read UNRELATED <<< "x"; echo hello', "read-into-unrelated-name-stays-allowed"),
    # False-positive guard for the round-28 fix to
    # `_names_reassigned_from_a_static_value` (issue #1375): the
    # round-27 form only ever ADDED to its own poisoned set, never
    # removed from it, so a name reassigned static -> dynamic -> static
    # again (a THIRD assignment fully restoring a trustworthy value)
    # stayed poisoned forever. Confirmed live via a stand-in `uv` binary
    # on PATH that `TOOL=uv; VERB=harmless; VERB=$(echo x); VERB=status;
    # $TOOL $VERB foo` genuinely runs `uv status foo` -- `status` is not
    # a watched verb.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo x); VERB=status; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-static-dynamic-static-stays-allowed",
    ),
    # Same round, the gh-api-write counterpart -- deliberately using a
    # read-method pair (GET/HEAD) that never triggers the SEPARATE,
    # deliberately sticky write-bias mechanism (round 22), which would
    # otherwise mask this specific fix's own effect. Confirmed live via
    # a stand-in `gh` binary on PATH that `M=GET; M=$(echo x); M=HEAD;
    # gh api repos/o/r/issues -X $M` genuinely runs `gh api
    # repos/o/r/issues -X HEAD`, a read method.
    (
        "M=GET; M=$(echo x); M=HEAD; gh api repos/o/r/issues -X $M",
        "gh-api-method-value-reassigned-static-dynamic-static-stays-allowed",
    ),
    # False-positive guard for the twenty-ninth-round `_segment_
    # references_a_name` indirect-reference fix (issue #1375): VERB is
    # genuinely poisoned (static "harmless" then dynamic "install"), but
    # the segment never references VERB itself -- only OTHER, indirectly,
    # through MREF. The two-level resolution the fix now delegates to
    # must not over-reach and treat every poisoned name anywhere in scope
    # as reachable through an unrelated indirection. Confirmed live via a
    # stand-in `uv` binary on PATH that this genuinely runs `uv status
    # foo` -- "status" is not a watched verb.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); OTHER=status; MREF=OTHER; $TOOL ${!MREF} foo",
        "indirect-ref-to-unrelated-name-stays-allowed-despite-a-poisoned-name-elsewhere",
    ),
    # False-positive guard for the thirtieth-round `_names_cleared_by_a_
    # later_static_reassignment` fix (issue #1375): round 28's own
    # "clear on later static reassignment" fix was applied only inside
    # `_names_reassigned_from_a_static_value`, leaving an append/`read`/
    # array-element reassignment poisoned forever even after a later,
    # fully-trustworthy static value. Confirmed live via a stand-in `uv`
    # binary on PATH that this genuinely runs `uv safe foo` -- "safe" is
    # not a watched verb.
    (
        "TOOL=uv; VERB=inst; VERB+=all; VERB=safe; $TOOL $VERB foo",
        "var-split-tool-and-verb-appended-then-given-a-later-static-value-stays-allowed",
    ),
    # Same round, the `read` counterpart.
    (
        "TOOL=uv; read VERB <<< status; VERB=safe; $TOOL $VERB foo",
        "var-split-tool-and-verb-read-into-then-given-a-later-static-value-stays-allowed",
    ),
    # Same round, the array-element-assignment counterpart.
    (
        "TOOL=uv; VERB[0]=install; VERB=safe; $TOOL $VERB foo",
        "var-split-tool-and-verb-array-element-assigned-then-given-a-later-static-value-stays-allowed",
    ),
    # Same round, the gh-api-write counterpart: real bash genuinely runs
    # `gh api repos/o/r/issues -X GET`, a read method.
    (
        "M=P; M+=OST; M=GET; gh api repos/o/r/issues -X $M",
        "gh-api-method-value-appended-then-given-a-later-static-value-stays-allowed",
    ),
    # False-positive guards for the thirty-first-round subshell-scoping
    # fix (issue #1375): an ordinary, unrelated subshell elsewhere in the
    # command must not spuriously deny a command whose watched name was
    # never poisoned at all, and a harmless subshell assignment earlier
    # in the command must not block a LATER, genuine top-level static
    # reassignment from clearing poisoning normally.
    (
        "TOOL=uv; VERB=safe; (echo hi); $TOOL $VERB foo",
        "unrelated-harmless-subshell-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; (VERB=harmless); VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-a-harmless-subshell-stays-allowed",
    ),
    # False-positive guards for the thirty-second-round scope-isolation
    # generalization (issue #1375): an ordinary, unrelated pipeline,
    # background job, or function call elsewhere in the command must not
    # spuriously deny a command whose watched name was never poisoned at
    # all, and a harmless pipeline earlier in the command must not block
    # a LATER, genuine top-level static reassignment from clearing
    # poisoning normally.
    (
        "TOOL=uv; VERB=safe; true | cat; $TOOL $VERB foo",
        "unrelated-harmless-pipeline-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=safe; sleep 0 & wait; $TOOL $VERB foo",
        "unrelated-harmless-background-job-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; f() { echo hi; }; f; VERB=safe; $TOOL $VERB foo",
        "unrelated-harmless-function-call-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; g() { VERB=notlocal; }; VERB=safe; $TOOL $VERB foo",
        "unrelated-function-bodys-own-plain-non-local-assignment-does-not-interfere",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); true | echo hi; VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-a-harmless-pipeline-stays-allowed",
    ),
    # False-positive guards for the thirty-third-round process-
    # substitution and declare/typeset fixes (issue #1375): an ordinary,
    # unrelated process substitution elsewhere in the command, or a
    # top-level `declare` (never inside a function, so real bash treats
    # it as an ordinary global assignment) on a name that was never
    # poisoned, must not spuriously deny -- and a harmless process
    # substitution earlier in the command must not block a LATER,
    # genuine top-level static reassignment from clearing normally.
    (
        "TOOL=uv; VERB=safe; cat <(echo hi) >/dev/null; $TOOL $VERB foo",
        "unrelated-harmless-process-substitution-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; declare VERB=safe; $TOOL $VERB foo",
        "top-level-declare-that-was-never-poisoned-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); cat <(echo hi) >/dev/null; VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-a-harmless-process-substitution-stays-allowed",
    ),
    # False-positive guards for the thirty-fourth-round coproc and
    # `$"local"` fixes (issue #1375): an ordinary, unrelated coproc
    # elsewhere in the command must not spuriously deny a command whose
    # watched name was never poisoned at all, an ordinary `$local`
    # variable reference (not the `$"local"` locale-string form) in a
    # DIFFERENT segment must not either, and a harmless coproc earlier in
    # the command must not block a LATER, genuine top-level static
    # reassignment from clearing normally.
    (
        "TOOL=uv; VERB=safe; coproc { echo hi; }; wait; $TOOL $VERB foo",
        "unrelated-harmless-coproc-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; echo $local; VERB=safe; $TOOL $VERB foo",
        "unrelated-plain-dollar-local-variable-reference-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); coproc { echo hi; }; wait; VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-a-harmless-coproc-stays-allowed",
    ),
    # No-over-correction guards for the thirty-fifth-round group-isolation
    # fix (issue #1375): a bare `{...}`/`if`/`for` compound command with NO
    # trailing `&`/`|` genuinely LEAKS its assignments to the parent shell
    # in real bash (confirmed live: each variant's stand-in `uv` call
    # captures `uv called with: safe foo`, not `install foo`) -- these must
    # stay allowed exactly as before this round's fix.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); { VERB=safe; }; $TOOL $VERB foo",
        "bare-brace-group-with-no-trailing-background-or-pipe-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); if true; then VERB=safe; fi; $TOOL $VERB foo",
        "bare-if-with-no-trailing-background-or-pipe-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); for i in 1; do VERB=safe; done; $TOOL $VERB foo",
        "bare-for-loop-with-no-trailing-background-or-pipe-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=safe; { echo hi; } & wait; $TOOL $VERB foo",
        "unrelated-harmless-backgrounded-brace-group-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); { echo hi; } & wait; VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-a-harmless-backgrounded-brace-group-stays-allowed",
    ),
    # No-over-correction guards for the thirty-sixth-round case/esac
    # group-isolation fix (issue #1375): a bare `case ... esac` with NO
    # trailing `&`/`|` genuinely LEAKS its assignment to the parent shell
    # in real bash (confirmed live: `uv called with: safe foo`), a
    # GENUINE `(...)` subshell nested inside a case arm's own body must
    # still decrement depth normally once that arm's own pattern-
    # terminating `)` has already been consumed, and an unrelated,
    # never-poisoned name must not be spuriously denied by a harmless
    # case elsewhere in the command.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); case 1 in 1) VERB=safe ;; esac; $TOOL $VERB foo",
        "bare-case-with-no-trailing-background-or-pipe-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); "
        "case 1 in 1) ( VERB=x ); true ;; esac; VERB=safe; $TOOL $VERB foo",
        "real-subshell-nested-inside-a-case-arm-that-genuinely-leaks-after-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=safe; case 1 in 1) echo hi ;; esac & wait; $TOOL $VERB foo",
        "unrelated-harmless-backgrounded-case-alongside-a-never-poisoned-name-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); case 1 in 1) echo hi ;; esac & wait; VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-a-harmless-backgrounded-case-stays-allowed",
    ),
    # FALSE-POSITIVE fix found live by Step 8 independent review,
    # thirty-seventh round (issue #1375): bash's `case` syntax allows an
    # OPTIONAL leading `(` decorator on a pattern arm (`(1) cmd ;;`,
    # `(1|2) cmd ;;` -- common, POSIX/ksh-compatible style, no `shopt`
    # needed) -- lexically identical to a real subshell opener, but the
    # round-36 fix only consulted its own case-tracking state on the
    # CLOSING paren, never the opening one, so the decorator's own
    # phantom depth increment was never balanced, permanently inflating
    # tracked depth and wrongly denying an unrelated, genuinely
    # top-level static reassignment later in the command. Confirmed live
    # via a stand-in `uv`/`gh` binary on PATH that each genuinely runs
    # the harmless, cleared value.
    (
        "TOOL=uv; VERB=inst; VERB+=all; case 1 in (1) true ;; esac; VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-a-harmless-bare-decorated-case-stays-allowed",
    ),
    (
        "TOOL=uv; VERB=inst; VERB+=all; case 2 in (1|2) true ;; esac; VERB=safe; $TOOL $VERB foo",
        "real-top-level-static-clear-after-an-alternation-decorated-case-stays-allowed",
    ),
]

# --- Known, disclosed, unresolved regex/token-gate bypasses ----------------
# This script shares the same cmd_boundary/whitespace-anchored regex
# construction that skills/executing-a-branch-plan/scripts/
# check_task_bash_safety.sh was adapted from -- but its own
# KNOWN_BYPASS_COMMANDS list below is NOT identical to the sibling test
# file's own list. This file's list has 3 entries; the sibling's has 4.
# Only one case-id is shared verbatim between the two:
# "array-literal-assignment-indirection". This file's other two entries
# (string-slice-reconstruction-uv-install, graphql-mutation-keyword-
# variable-concatenation) and the sibling's other three (its own
# pip-specific string-slice case, string-slice-reconstruction-pip-install,
# plus fetch-exec-sudo-separate-value-flag-not-skipped and
# array-literal-subscript-of-a-real-array-whose-own-element-is-empty)
# each have no matching case-id in the other file's list. This script is
# confirmed bypassed by its own 3 entries below (verified directly: all
# 3 return exit 0/unblocked against this script), but neither this
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
    (
        # Issue #1375's own checkout/restore path extraction closes every
        # ORDINARY, honest-accident-shaped way a decoy token between `git`
        # and `checkout`/`restore` vanishes at real bash runtime: a bare
        # `$NAME`/`${NAME}` reference, and the default/assign-default/
        # alt-value clause forms (`${NAME:-}`/`${NAME-}`, `${NAME:=}`/
        # `${NAME=}`, `${NAME:+x}`/`${NAME+x}`) -- all common defensive-
        # scripting idioms for "reference a variable that might not be
        # set." Bash's OTHER parameter-expansion operators that also
        # evaluate to the empty string on an unset variable -- substring
        # (`${NAME:0:5}`), prefix/suffix removal (`${NAME#x}`/
        # `${NAME%x}`), pattern substitution (`${NAME/x/y}`), and case
        # modification (`${NAME^^}`) among others -- are NOT recognized:
        # confirmed live these are not honest-accident-shaped the way the
        # closed forms are (an ordinary script does not reach for prefix
        # removal or case-folding just to guard against an unset
        # variable), matching this file's own established convention for
        # "exotic non-literal indirection" (issue #1375's own Non-goals
        # section) rather than the near-zero-effort, ordinary-idiom bypass
        # class the closed forms addressed. Confirmed live: this decoy is
        # NOT silently allowed as if `checkout` were genuinely resolved --
        # the `git` occurrence is correctly treated as ambiguous and the
        # command is simply never recognized as a checkout/restore
        # invocation at all (checkout_restore_paths stays empty, matching
        # the SAME disclosed-residual shape `V=checkout; git $V -- f.py`
        # already carries), not a distinct or worse failure mode.
        "git ${NEVERSET#x} checkout -- file.py",
        "checkout-restore-exotic-parameter-expansion-decoy",
    ),
    (
        # Found live by independent adversarial review (round 4, issue
        # #1375): `-b`/`-B`/`--orphan` is git's own branch-creation mode,
        # mutually exclusive with every pathspec-checkout mode -- but
        # `-b`/`-B` take the immediately following token as their own
        # new-branch-NAME value, which does not start with `-`, so this
        # command used to sweep "newbranch"/"other" into
        # `checkout_restore_paths` as if they were file paths instead of
        # the actual at-risk file. Live-verified before the fix: the
        # wrapper's check against those two nonexistent paths found
        # "clean" and allowed a real, forced branch switch through that
        # silently discarded an uncommitted change elsewhere. Now folded
        # into the same honest, no-claim Non-goal `git checkout SOMENAME`
        # already carries (empty `checkout_restore_paths`, not a false
        # claim) -- disambiguating a branch-creation/reset's own working-
        # tree impact soundly would need to reproduce git's internal
        # "would this overwrite ANY dirty tracked file" logic, out of a
        # pure classifier's reach, the same reasoning that already accepts
        # the bare-SOMENAME case as a Non-goal rather than a sound
        # extraction.
        "git checkout -f -b newbranch other",
        "checkout-branch-creation-flag-non-goal",
    ),
    (
        # CRITICAL, WHOLE-MODULE bypass -- NOT specific to checkout/restore
        # or to this file's own KNOWN_BYPASS_COMMANDS convention's usual
        # narrow-decoy shape. Found live by independent adversarial review
        # (round 8, issue #1375), tracked as its own dedicated issue rather
        # than fixed here: https://github.com/tvna/gitapex/issues/1404 --
        # deliberately out of issue #1375's own scope, since the root cause
        # predates it, is architectural (Python's `shlex` tracks
        # double-quote state as one flat, whole-command toggle with no
        # concept of bash's own recursive quote-context reset inside a
        # `$(...)` command substitution), and is shared by EVERY rule in
        # this file, not just checkout/restore. A double-quoted span
        # nested inside a `$(...)` that is itself nested inside an outer
        # double-quoted string desynchronizes `shlex`'s quote parity from
        # real bash's own parse while keeping the TOTAL quote-character
        # count even, so `tokenize()`'s own `TokenizeError` fail-closed
        # path never fires (unlike the structurally-safe, always-
        # unbalanced quote-decoy case the round-7 fix's own docstring
        # already documents). Live-verified real, silent data loss: this
        # exact command genuinely discards a dirty tracked file named
        # `dirty.py` when actually executed, while `classify()` reports
        # `deny=False` with an EMPTY `checkout_restore_paths` -- "git"
        # and "checkout" never appear as their own separate tokens at all,
        # fused into an inert-looking quoted blob by `shlex`'s own
        # mis-toggled state. See issue #1404 for the full write-up,
        # live-verification detail, and why a genuine fix needs a
        # command-substitution-aware recursive tokenizer rather than a
        # narrow patch.
        'x="$(echo "y)" && git checkout -- dirty.py)"',
        "shlex-nested-double-quote-inside-command-substitution-full-bypass",
    ),
    (
        # CRITICAL bypass, same underlying shlex-quote-information-loss
        # class as the residual just above. Found live by independent
        # adversarial review (round 17, issue #1375), tracked as its own
        # dedicated issue rather than fixed here:
        # https://github.com/tvna/gitapex/issues/1412 -- deliberately out
        # of issue #1375's own scope, since a narrow fix confined to the
        # redirect-handling functions alone does not exist without
        # reintroducing round 15's own, far more common false positive
        # (denying an ordinary `git checkout -- f.py >> log.txt`-style
        # output redirect); a genuine fix needs tokenize() itself to
        # preserve per-token quote/escape provenance, the same class of
        # tokenizer-level change issue #1404 already requires.
        # `_REDIRECT_OPERATORS`/`_strip_redirect_clauses` recognize a
        # redirect operator purely by a token's final TEXT value --
        # `tokenize()`'s own shlex dequotes every token first, so a real,
        # tracked file literally named `>` tokenizes identically to a
        # genuine, unquoted redirect operator. Live-verified real, silent
        # data loss: with a real tracked file literally named `>` and a
        # second, genuinely dirty file `realfile.py`, this exact command
        # discards `realfile.py`'s uncommitted content when actually
        # executed, while `classify()` reports `deny=False` with an EMPTY
        # `checkout_restore_paths` -- the quoted `">"` is misread as a
        # real operator and `realfile.py` as its "target," stripping both
        # and leaving nothing to extract. See issue #1412 for the full
        # write-up and live-verification detail.
        'git checkout ">" realfile.py',
        "quoted-redirect-operator-shaped-filename-bypass",
    ),
    (
        # CRITICAL bypass, third instance of the same underlying
        # shlex-quote-information-loss class as the two residuals above.
        # Found live by independent adversarial review (round 39, issue
        # #1375), tracked as its own dedicated issue rather than fixed
        # here: https://github.com/tvna/gitapex/issues/1502 --
        # deliberately out of issue #1375's own scope, for the identical
        # reason issue #1412 already gives: a narrow patch confined to
        # `_raw_segments_with_boundaries` alone risks reintroducing a
        # worse, far more common false-positive class; a genuine fix
        # needs tokenize() itself to preserve per-token quote/escape
        # provenance, the same class of tokenizer-level change issues
        # #1404/#1412 already require. `_raw_segments_with_boundaries`
        # recognizes a real subshell close purely by a token's final TEXT
        # value (`tok == ")"`) -- `tokenize()`'s own shlex dequotes every
        # token first, so a QUOTED `")"` argument inside a genuinely
        # enclosing `(...)` subshell tokenizes identically to a real,
        # unquoted subshell-closing paren, prematurely decrementing
        # tracked depth. Live-verified: real bash genuinely still runs
        # `uv install foo` (`VERB=safe` never escapes the real subshell),
        # while `classify()` reports `deny=False`. See issue #1502 for
        # the full write-up, the companion false-positive shape, and
        # live-verification detail.
        'TOOL=uv; VERB=harmless; VERB=$(echo install); ( true ")" ; VERB=safe ); $TOOL $VERB foo',
        "quoted-paren-inside-a-subshell-clears-a-poisoning-bypass",
    ),
    (
        # Companion to the bypass just above, for `_rule_gh_api_write`.
        # See issue #1502.
        'M=safe; M=$(echo POST); ( true ")" ; M=GET ); gh api repos/o/r/pulls/1/merge -X $M',
        "gh-api-quoted-paren-inside-a-subshell-clears-a-poisoning-bypass",
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
    # Found live by Step 8 independent review, sixteenth round (issue
    # #1326): a fully literal, undisguised denied verb sequence hidden
    # inside bash's own array-literal syntax, invisible to every rule
    # once an earlier version of `_fold_array_literal_spans` folded the
    # array's own element list into one opaque, space-free token that
    # `_strip_leading_assignments` then discarded whole as an ordinary
    # (inert) assignment -- confirmed live that pre-round-15 (before
    # array-literal folding existed at all) the identical construction
    # was correctly denied, and that a stub tool on PATH genuinely runs
    # via `bash -c` once `"${A[@]}"` expands the array.
    ('declare -a A=(pip install foo); "${A[@]}"', "array-literal-non-leading-hides-pip-install"),
    ('A=(gh pr merge 1); "${A[@]}"', "array-literal-leading-hides-gh-pr-merge"),
    # Found live by Step 8 independent review, sixteenth round (issue
    # #1326): `-X`/`--method` fused directly with `=` in ONE token
    # (`-X=POST`) was invisible to `_gh_api_method_literal_hit`'s own
    # fused-directly branch, which checked the raw suffix without first
    # stripping a leading `=` the way its sibling `_gh_api_method_
    # dynamic_value` already did for the identical shape -- confirmed
    # against `gh`'s own flag-parsing library (pflag) that a single
    # fused argv token `-X=POST` genuinely parses to a real write.
    ("gh api repos/o/r/issues/1 -X=POST", "gh-api-method-fused-equals-literal"),
    # The dynamic-flagname counterpart of the case immediately above:
    # `"$F"=POST` tokenizes to one fused token `$F=POST`, never reaching
    # `_gh_api_method_literal_hit`'s own literal-token scan at all --
    # denied instead by `_gh_api_method_fused_flagname_dynamic_hit`'s own
    # sixteenth-round `.lstrip("=")` fix of the identical gap on a
    # resolved candidate string.
    ('F=-X; gh api repos/o/r/issues/1 "$F"=POST', "gh-api-method-fused-equals-dynamic-flagname"),
    # Found live by Step 8 independent review, seventeenth round (issue
    # #1326): an earlier version of `_fold_array_literal_spans` folded
    # an array-literal span whenever ANY of its own elements was
    # dynamic, not just the first -- a single unrelated dynamic element
    # anywhere in the array (a stray `$Y`, a trailing `$(echo 1)`) folded
    # the WHOLE span into one opaque token, hiding fully literal,
    # undisguised denied-verb tokens sitting right next to it. Confirmed
    # live via a real bash proxy (stand-in `uv`/`gh` binaries on PATH,
    # capturing their own argv) that both genuinely invoke the denied
    # tool once `"${A[@]}"` expands.
    ('Y=1; A=(uv install $Y); "${A[@]}"', "array-literal-trailing-dynamic-element-hides-uv-install"),
    ('A=(gh pr merge $(echo 1)); "${A[@]}"', "array-literal-trailing-command-substitution-hides-gh-pr-merge"),
    # Found live by Step 8 independent review, eighteenth round (issue
    # #1326): a leading UNQUOTED reference to a variable never assigned
    # anywhere in the command word-splits away to NOTHING at real bash
    # runtime (confirmed live via `declare -p` that
    # `A=($NEVERSET gh pr merge 1)`, NEVERSET never assigned, produces a
    # 4-element array `(gh pr merge 1)` -- NEVERSET contributes zero
    # elements), so the array's own REAL first element is the denied
    # tool/verb right after it -- every prior round's own fold-condition
    # heuristic (unconditional; any-element-dynamic; first-element-
    # dynamic) treated the reference as an ordinary dynamic first
    # element and folded the whole span away, hiding the fully literal
    # content after it. `_rule_array_literal_content`'s own recursive,
    # fold-independent check (run before any folding) closes this.
    ('A=($NEVERSET uv install); "${A[@]}" foo', "array-literal-unassigned-leading-ref-hides-uv-install"),
    ('A=($NEVERSET gh pr merge 1); "${A[@]}"', "array-literal-unassigned-leading-ref-hides-gh-pr-merge"),
    # Found live by Step 8 independent review, nineteenth round (issue
    # #1326): the eighteenth round's own recursive `_rule_array_literal_
    # content` check dropped the OUTER command's own assigned variables
    # entirely when classifying an array literal's inner content, since
    # the recursive call re-derived name_to_value/name_to_raw_value from
    # the array's own inner tokens alone -- a tool/verb built from a
    # variable assigned OUTSIDE the array literal's own span was
    # invisible to it, even though it resolves at real bash runtime the
    # same as it would at the top level (confirmed live via `declare -p`
    # that `A=($G $P $M)` genuinely expands to `gh pr merge` once G/P/M
    # are assigned earlier in the same command). Closed by threading the
    # outer scope through the recursive `_classify_tokens` call.
    ('G=gh; P=pr; M=merge; A=($G $P $M); "${A[@]}" 1', "array-literal-outer-scope-vars-hide-gh-pr-merge"),
    # A braced `${NAME}` decoy is the same word-splitting-collapse shape
    # as an unbraced `$NAME` decoy (both word-split away to nothing when
    # NAME is never assigned) -- `_BARE_VAR_REF_RE` only matched the
    # unbraced form until this round, so the collapsed reading never ran
    # for this shape. Confirmed live via `declare -p`.
    ('A=(${NEVERSET} gh pr merge 1); "${A[@]}"', "array-literal-braced-unassigned-leading-ref-hides-gh-pr-merge"),
    # Found live by Step 8 independent review, twentieth round (issue
    # #1326): two further decoy shapes that word-split away to nothing at
    # real bash runtime the identical way a plain `$NAME`/`${NAME}`
    # reference does, neither recognized by the nineteenth round's own
    # `_BARE_VAR_REF_RE` -- a braced array-element subscript to an
    # unassigned NAME, and two-or-more bare/braced references FUSED into
    # one token with nothing else between them. Confirmed live via
    # `declare -p`.
    ('A=(${NEVERSET[0]} uv "$1"); "${A[@]}"', "array-literal-subscript-unassigned-leading-ref-hides-uv"),
    ('A=($A_UNSET$B_UNSET gh pr merge 1); "${A[@]}"', "array-literal-fused-unassigned-leading-refs-hide-gh-pr-merge"),
    # Found live by Step 8 independent review, twenty-first round (issue
    # #1326): B2 (`_rule_b2_watched_tool_dynamic_verb_position`) requires
    # a LITERAL `seg[0]` naming a watched tool -- a leading unassigned
    # reference at `seg[0]`, with NO array literal required at all,
    # blocked it from ever firing regardless of what followed. Confirmed
    # live via a real bash proxy (stand-in `uv` binary on PATH) that
    # `$NEVERSET uv install` genuinely invokes `uv install` once the
    # decoy word-splits away.
    ("$NEVERSET uv $VERB", "bare-unassigned-leading-ref-hides-b2-watched-tool"),
    # Found live by Step 8 independent review, twenty-second round (issue
    # #1326): `_gh_api_method_dynamic_value`/`_gh_api_method_flagname_
    # dynamic_hit` used to read the token immediately after the
    # `-X`/`--method` flag (or, for the flagname variant, immediately
    # after the resolved flag-name token) directly, assuming the value
    # always sits there -- a leading decoy interposed in that position
    # made both functions read the decoy itself as "the value," silently
    # missing the real, dynamically-resolved write method one position
    # further. Confirmed live via direct Python calls that `_value_
    # position_after` now skips the decoy and finds the real value.
    ("M=POST; gh api repos/o/r/pulls/1 -X $NEVERSET $M", "gh-api-method-value-past-leading-decoy"),
    ("F=-X; M=POST; gh api repos/o/r/pulls/1 $F $NEVERSET $M", "gh-api-method-flagname-value-past-leading-decoy"),
    # Found live by Step 8 independent review, twenty-ninth round (issue
    # #1326): the twenty-eighth round's own blanket `$IFS`-reassignment
    # rule made `_value_position_after`'s skip-loop treat a REAL dynamic
    # write-method value as a decoy to skip past merely because `$IFS`
    # was reassigned somewhere else in the command, missing the genuine
    # write entirely. Confirmed live via real bash that `IFS=x; echo hi;
    # M=POST; gh api repos/foo/bar/merge -X ${M} extra` real-expands to
    # `gh api repos/foo/bar/merge -X POST extra`, a genuine write.
    (
        "IFS=x; echo hi; M=POST; gh api repos/foo/bar/merge -X ${M} extra",
        "gh-api-method-value-past-unrelated-ifs-reassignment",
    ),
    # Found live by Step 8 independent review, thirtieth round (issue
    # #1326): the twenty-ninth round's own `effective_ifs` fix computed
    # it (and every per-name value stripped against it) from the
    # LOWERCASED name-to-value map -- real bash `$IFS` word-splitting is
    # case-SENSITIVE, so a value whose real (mixed-case) characters do
    # NOT overlap the real (differently-cased) reassigned `$IFS` was
    # wrongly read as vanishing once both were folded to the same case.
    # Confirmed live via real bash that `IFS=post; DECOY=POST; gh api
    # repos/foo/bar/merge -X ${DECOY} extra` real-expands to `gh api
    # repos/foo/bar/merge -X POST extra`, a genuine write.
    (
        "IFS=post; DECOY=POST; gh api repos/foo/bar/merge -X ${DECOY} extra",
        "gh-api-method-value-past-case-folded-ifs-collision",
    ),
    # Found live by Step 8 independent review, twenty-second round (issue
    # #1375, confirmed against issue #1326): B1a/B1b's own tool+verb
    # reconstruction and `_rule_gh_api_write`'s own dynamic -X/--method
    # resolution were both fed the ordinary, order-blind ASSIGNED/
    # RAW_ASSIGNED dicts -- the SAME reassignment-ambiguity class round
    # 19 (git-token) and round 20 (cd/pushd/popd-relocation) already
    # closed for the checkout/restore consumer, left open on these two
    # entirely different, HARD-DENY consumers. Confirmed live via a real
    # bash proxy (stand-in `uv`/`gh` binaries on PATH, capturing their own
    # argv): `$B` genuinely was "install" at its actual point of use one
    # statement earlier, and real bash genuinely ran `uv install foo`.
    ("A=uv; B=install; $A $B foo; B=somethingelse", "var-split-tool-and-verb-reassigned-after-use"),
    # Same round, the gh-api-write counterpart: `$M` genuinely was "POST"
    # at its actual point of use; real bash genuinely ran `gh api
    # repos/o/r/pulls/1/merge -X POST` -- a genuine, unreviewed write API
    # call (e.g. merging a pull request).
    ("M=POST; gh api repos/o/r/pulls/1/merge -X $M; M=safe", "gh-api-method-value-reassigned-after-use"),
    # Round 22's own OR-fallback fix threads the write-biased dict through
    # the SAME recursive chain rounds 19-21 already use, not merely the
    # top-level segment scope -- confirms the reassignment straddling a
    # command substitution's OWN boundary (the ambiguity living in the
    # OUTER token stream, the tool+verb pair used entirely WITHIN the
    # substitution) is closed too, mirroring round 21's own correction of
    # round 20's initially-scoped-down cd-biased fix.
    (
        "A=uv; x=$($A install foo); A=somethingelse",
        "var-split-tool-and-verb-reassigned-after-use-across-command-substitution",
    ),
    # Found live by Step 8 independent review, twenty-sixth round (issue
    # #1375): neither `_ASSIGN_RE` nor `_APPEND_ASSIGN_RE` recognizes
    # bash's own `read NAME` builtin or `NAME[i]=value` array-element
    # assignment as a reassignment at all -- round 22's own fix (the two
    # cases immediately above) only closed the reassignment-ambiguity gap
    # for RECOGNIZED assignment tokens (plain `=`/`+=`), leaving both of
    # these completely unrecognized shapes open. Confirmed live via a
    # stand-in `uv` binary on PATH (captured argv: "install foo") that
    # `A=harmless; read A <<< "uv"; B=harmless2; read B <<< "install"; $A
    # $B foo` genuinely runs `uv install foo`.
    (
        'A=harmless; read A <<< "uv"; B=harmless2; read B <<< "install"; $A $B foo',
        "var-split-tool-and-verb-reassigned-via-read",
    ),
    # Same round, the array-element-assignment counterpart.
    (
        "A=harmless; A[0]=uv; B=harmless2; B[0]=install; $A $B foo",
        "var-split-tool-and-verb-reassigned-via-array-element",
    ),
    # Same round, the gh-api-write counterpart for `read`: `$M` genuinely
    # was "POST" at its actual point of use; real bash genuinely ran `gh
    # api repos/o/r/pulls/1/merge -X POST`.
    (
        'M=GET; read M <<< "POST"; gh api repos/o/r/pulls/1/merge -X $M',
        "gh-api-method-value-reassigned-via-read",
    ),
    # Same round, the gh-api-write counterpart for array-element
    # assignment.
    ("M=GET; M[0]=POST; gh api repos/o/r/pulls/1/merge -X $M", "gh-api-method-value-reassigned-via-array-element"),
    # Same round, the `printf -v` counterpart (writes a formatted result
    # into NAME, equally invisible to `_ASSIGN_RE`/`_APPEND_ASSIGN_RE`).
    (
        'M=GET; printf -v M "%s" POST; gh api repos/o/r/pulls/1/merge -X $M',
        "gh-api-method-value-reassigned-via-printf-v",
    ),
    # Found live by Step 8 independent review, twenty-seventh round
    # (issue #1375): round 26's own fix (the two `_names_reassigned_by_
    # untracked_construct` cases just above) deliberately excluded the
    # round-24 plain-dynamic-reassignment and round-25 append classes
    # ENTIRELY from B1a/B1b and gh-api-write, not just their genuinely-
    # unresolvable sub-case -- leaving a name with an earlier STATIC
    # value, later reassigned dynamically, with NO protection at all.
    # Confirmed live via a stand-in `uv` binary on PATH (captured argv:
    # "install foo") that `TOOL=uv; VERB=harmless; VERB=$(echo install);
    # $TOOL $VERB foo` genuinely runs `uv install foo`.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value",
    ),
    # Same round, the append counterpart.
    (
        "TOOL=uv; VERB=inst; VERB+=all; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-via-static-append",
    ),
    # Same round, the gh-api-write counterpart: real bash genuinely ran
    # `gh api repos/o/r/pulls/1/merge -X POST` (captured argv confirms
    # it), a genuine, unreviewed write API call.
    (
        "M=safe; M=$(echo POST); gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value",
    ),
    # Round 28's own no-under-correction guard: a name that carries a
    # watched write method (POST) at ANY point must stay denied even
    # after a later, static reassignment to a read method (GET) --
    # `_assigned_raw_values_biased_toward`'s own independent, sticky
    # write-bias mechanism (round 22) must keep denying this regardless
    # of round 28's own fix to a SEPARATE mechanism (`_names_reassigned_
    # from_a_static_value`'s own poisoned-set clearing).
    (
        "M=POST; M=$(echo x); M=GET; gh api repos/o/r/issues -X $M",
        "gh-api-method-value-ever-a-watched-write-method-stays-denied",
    ),
    # Found live by Step 8 independent review, twenty-ninth round (issue
    # #1375): `_segment_references_a_name`'s own round-26 single-level
    # `${!NAME}` indirect-reference scan defeated EVERY poisoning class
    # above (static-then-dynamic, append, read/array-element/printf-v)
    # once the poisoned name was referenced through one extra layer of
    # indirection -- the direct reference (no `${!MREF}`) already denied
    # correctly; only wrapping it in an indirect reference bypassed
    # detection. Confirmed live via a stand-in `uv` binary on PATH
    # (captured argv: "install foo") that this genuinely runs `uv install
    # foo`.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); MREF=VERB; $TOOL ${!MREF} foo",
        "var-split-tool-and-verb-reassigned-from-static-referenced-indirectly",
    ),
    # Same round, the append counterpart referenced indirectly.
    (
        "TOOL=uv; VERB=inst; VERB+=all; MREF=VERB; $TOOL ${!MREF} foo",
        "var-split-tool-and-verb-reassigned-via-static-append-referenced-indirectly",
    ),
    # Same round, the `read` counterpart referenced indirectly.
    (
        'A=harmless; read A <<< "uv"; B=harmless2; read B <<< "install"; AREF=A; BREF=B; ${!AREF} ${!BREF} foo',
        "var-split-tool-and-verb-reassigned-via-read-referenced-indirectly",
    ),
    # Same round, the gh-api-write counterpart: real bash genuinely ran
    # `gh api repos/o/r/pulls/1/merge -X POST` (captured argv confirms
    # it), a genuine, unreviewed write API call.
    (
        "M=safe; M=$(echo POST); MREF=M; gh api repos/o/r/pulls/1/merge -X ${!MREF}",
        "gh-api-method-value-reassigned-from-a-static-value-referenced-indirectly",
    ),
    # Found live by Step 8 independent review, thirtieth round (issue
    # #1375): the round-30 no-under-correction guard -- a name given a
    # static value and THEN appended to must stay denied, since the
    # append (not the earlier static value) is the name's latest
    # assignment-class event and its own combined value is still
    # unrecoverable in general, exactly as round 25's own original
    # "poison unconditionally on any append" posture already requires.
    # Confirmed live via a stand-in `uv` binary on PATH that this
    # particular instance happens to resolve to the harmless `uv safex
    # foo` -- the classifier's own deliberately conservative posture
    # correctly denies it anyway, since it cannot in general predict a
    # concatenation's own final value from a static prefix and a
    # dynamic append alone.
    (
        "TOOL=uv; VERB=safe; VERB+=x; $TOOL $VERB foo",
        "var-split-tool-and-verb-given-a-static-value-then-appended-to-stays-denied",
    ),
    # Found live by Step 8 independent review, thirty-first round (issue
    # #1375): `_names_reassigned_from_a_static_value` and `_names_
    # cleared_by_a_later_static_reassignment` were both completely blind
    # to bash's own subshell scoping -- a `(...)` grouping runs in a
    # forked, isolated shell whose own assignments never propagate back
    # to the parent, but both functions' own flat/per-segment scans
    # treated a static assignment written INSIDE `(...)` exactly like an
    # ordinary top-level one, letting it wrongly clear a genuinely
    # poisoned name. Confirmed live via a stand-in `uv` binary on PATH
    # that this genuinely runs `uv install foo`, NOT `safe foo` -- the
    # parenthesized `VERB=safe` never reaches the parent shell's own
    # `$VERB` at all.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); (VERB=safe); $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-subshell",
    ),
    # Same round, the append counterpart.
    (
        "TOOL=uv; VERB=inst; VERB+=all; (VERB=safe); $TOOL $VERB foo",
        "var-split-tool-and-verb-appended-then-cleared-via-a-subshell",
    ),
    # Same round, the array-element-assignment counterpart.
    (
        "TOOL=uv; VERB=x; VERB[0]=install; (VERB=safe); $TOOL $VERB foo",
        "var-split-tool-and-verb-array-element-assigned-then-cleared-via-a-subshell",
    ),
    # Same round, the `read` counterpart.
    (
        "TOOL=uv; read VERB <<< install; (VERB=safe); $TOOL $VERB foo",
        "var-split-tool-and-verb-read-into-then-cleared-via-a-subshell",
    ),
    # Same round, the gh-api-write counterpart: real bash genuinely runs
    # `gh api repos/o/r/pulls/1/merge -X POST`, a genuine unreviewed
    # write API call (e.g. merging a pull request).
    (
        "M=safe; M=$(echo POST); (M=GET); gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-subshell",
    ),
    # Found live by Step 8 independent review, thirty-second round (issue
    # #1375): round 31's own subshell-scoping fix covered ONLY `(...)`
    # grouping, leaving three sibling scope-isolating bash constructs
    # equally exploitable via the identical trick. Confirmed live via a
    # stand-in `uv`/`gh` binary on PATH that each genuinely runs the
    # dangerous command, NOT the parenthesized/piped/backgrounded/local
    # distractor value.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); true | VERB=safe; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-pipe-stage",
    ),
    (
        "M=safe; M=$(echo POST); true | M=GET; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-pipe-stage",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); VERB=safe & wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-background-job",
    ),
    (
        "M=safe; M=$(echo POST); M=GET & wait; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-background-job",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); f() { local VERB=safe; }; f; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-local-declaration",
    ),
    (
        "M=safe; M=$(echo POST); f() { local M=GET; }; f; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-local-declaration",
    ),
    # Same round, the disclosed arithmetic-vs-double-subshell ambiguity
    # residual: `((VERB=1))` stays denied on purpose (see `_segment_
    # tokens_with_scope_isolation`'s own docstring for why the naive fix
    # was rejected as unsafe), and a genuinely double-nested, spaced
    # subshell carrying a distractor value must stay denied too.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); ((VERB=1)); $TOOL $VERB foo",
        "arithmetic-double-paren-content-stays-denied-as-a-disclosed-residual",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); ( (VERB=totallysafe) ); $TOOL $VERB foo",
        "deliberately-spaced-double-subshell-distractor-stays-denied",
    ),
    # Found live by Step 8 independent review, thirty-third round (issue
    # #1375): process substitution (`<(...)`/`>(...)`) runs its own
    # content in a separate, isolated subshell, exactly like `$(...)`
    # command substitution, but this classifier's own tokenizer fuses
    # `<(`/`>(` into their own distinct tokens, never a bare `(` -- the
    # pre-round-33 code neither isolated its content nor correctly
    # paired its matching close, corrupting depth tracking for a
    # genuinely enclosing real subshell too. `declare`/`typeset` used
    # INSIDE a function body also implicitly localize a variable exactly
    # like `local` does, which the pre-round-33 code had no concept of.
    # Confirmed live via a stand-in `uv`/`gh` binary on PATH that each
    # genuinely runs the dangerous command, NOT the process-substitution/
    # declare-scoped distractor value.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); cat <(VERB=safe) >/dev/null; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-process-substitution",
    ),
    (
        "M=safe; M=$(echo POST); cat <(M=GET) >/dev/null; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-process-substitution",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); (cat <(true); VERB=safe); $TOOL $VERB foo",
        "process-substitution-does-not-corrupt-an-enclosing-subshells-depth",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); f() { declare VERB=safe; }; f; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-declare-declaration",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); f() { typeset VERB=safe; }; f; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-typeset-declaration",
    ),
    (
        "M=safe; M=$(echo POST); f() { declare M=GET; }; f; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-declare-declaration",
    ),
    # Found live by Step 8 independent review, thirty-fourth round (issue
    # #1375): `coproc { ... }` forks its body to run asynchronously in a
    # subshell connected by a pipe, exactly like `cmd &`, with no
    # non-isolating usage at all -- the pre-round-34 isolation check had
    # no concept of `coproc` whatsoever. Bash's `$"..."` locale-
    # translated-string syntax also fuses the `$` prefix onto the
    # dequoted string content -- `$"local"` tokenizes as a single token
    # `$local`, never a bare `local`, but genuinely invokes the `local`
    # builtin in command-starting position. Confirmed live via a stand-in
    # `uv`/`gh` binary on PATH that each genuinely runs the dangerous
    # command, NOT the coproc/`$"local"`-scoped distractor value.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); coproc { VERB=safe; }; wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-coproc",
    ),
    (
        "M=safe; M=$(echo POST); coproc { M=GET; }; wait; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-coproc",
    ),
    (
        'TOOL=uv; VERB=harmless; VERB=$(echo install); f() { $"local" VERB=safe; }; f; $TOOL $VERB foo',
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-dollar-quoted-local",
    ),
    (
        'M=safe; M=$(echo POST); f() { $"local" M=GET; }; f; gh api repos/o/r/pulls/1/merge -X $M',
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-dollar-quoted-local",
    ),
    # Found live by Step 8 independent review, thirty-fifth round (issue
    # #1375): none of `{`, `}`, `while`, `do`, `done`, `until`, `for`,
    # `select`, `if`, `then`, `fi` were recognized by the scope-isolation
    # check at all -- but a `{...}` brace group or a `while`/`until`/
    # `for`/`select`/`if` compound command, backgrounded or piped AS A
    # WHOLE, forks exactly like a subshell. Confirmed live via a stand-in
    # `uv`/`gh` binary on PATH that each genuinely runs the dangerous
    # command, NOT the group-scoped distractor value.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); { VERB=safe; } & wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-backgrounded-brace-group",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); { VERB=safe; } | cat; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-piped-brace-group",
    ),
    (
        "M=safe; M=$(echo POST); { true; M=GET; } & wait; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-backgrounded-brace-group",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); while true; do VERB=safe; break; done | cat; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-piped-while-loop",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); if true; then VERB=safe; fi & wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-backgrounded-if",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); for i in 1; do VERB=safe; done & wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-backgrounded-for-loop",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); { { VERB=safe; }; } | cat; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-doubly-nested-piped-brace-group",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); echo x | { true; VERB=safe; }; wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-pipe-receiving-groups-second-statement",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); { echo fi; VERB=safe; } & wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-brace-group-containing-a-literal-fi-argument",
    ),
    # Found live by Step 8 independent review, thirty-sixth round (issue
    # #1375): `case ... esac` is bash's remaining compound-command form
    # -- it forks as one unit when backgrounded or piped, exactly like
    # `{...}`/`while`/`until`/`for`/`select`/`if` (round 35), but
    # `case`/`esac` were never added to the group-isolation keyword
    # sets. Separately, a case arm's own pattern-terminating `)` is
    # lexically indistinguishable from a subshell-closing `)` and was
    # unconditionally decrementing `(...)`-nesting depth, corrupting
    # tracking for a genuinely enclosing real subshell -- reproducing
    # with no `&`/`|` at all. Confirmed live via a stand-in `uv`/`gh`
    # binary on PATH that each genuinely runs the dangerous command,
    # NOT the case-scoped distractor value.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); case 1 in 1) VERB=safe ;; esac & wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-backgrounded-case",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); case 1 in 1) VERB=safe ;; esac | cat; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-piped-case",
    ),
    (
        "M=safe; M=$(echo POST); case 1 in 1) M=GET ;; esac & wait; gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-backgrounded-case",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); ( case 1 in 1) true ;; esac; VERB=safe ); $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-case-in-subshell-depth-corruption",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); "
        "( case 1 in 1) for i in 1; do true; done ;; esac; VERB=safe ); $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-case-in-subshell-with-a-nested-for-in-not-desyncing",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); "
        "case A in x) case B in y) VERB=safe;; esac ;; esac | cat; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-nested-case-whose-outer-is-piped",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); case 1 in (1) VERB=safe ;; esac & wait; $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-backgrounded-decorated-case",
    ),
    # CRITICAL bypass found live by Step 8 independent review,
    # thirty-eighth round (issue #1375): `case`/`esac` are only reserved
    # words in COMMAND-starting position -- the case statement's own
    # SUBJECT word (between `case` and `in`) is an ordinary word
    # position where a literal `esac` (or `case`) is valid, unremarkable
    # bash. The round-36/37 case-tracking state machine matched purely
    # on token text with no position check, so a literal `esac` subject
    # immediately popped the tracking stack before the real `in` was
    # even reached, corrupting a GENUINELY enclosing real subshell's own
    # tracked depth. Confirmed live via a stand-in `uv`/`gh` binary on
    # PATH that each genuinely keeps the reassignment isolated inside
    # the real subshell.
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); ( case esac in a) true ;; esac; VERB=safe ); $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-case-subject-word-matching-esac",
    ),
    (
        "M=safe; M=$(echo POST); ( case esac in a) true ;; esac; M=GET ); gh api repos/o/r/pulls/1/merge -X $M",
        "gh-api-method-value-reassigned-from-a-static-value-cleared-via-a-case-subject-word-matching-esac",
    ),
    (
        "TOOL=uv; VERB=harmless; VERB=$(echo install); ( case case in a) true ;; esac; VERB=safe ); $TOOL $VERB foo",
        "var-split-tool-and-verb-reassigned-from-a-static-value-cleared-via-a-case-subject-word-matching-case",
    ),
    # Same round (39), the disclosed quoted-open-paren over-denial
    # residual (issue #1502): a quoted "(" with no matching close
    # inflates tracked subshell depth for the rest of the command,
    # wrongly denying an ordinary, harmless, genuinely top-level
    # clearing reassignment that follows. See `_raw_segments_with_
    # boundaries`'s own module-docstring disclosure and the companion
    # `quoted-paren-inside-a-subshell-clears-a-poisoning-bypass` entry
    # above (the bypass direction of the same shlex-quote-information-
    # loss class).
    (
        'TOOL=uv; VERB=harmless; VERB=$(echo install); echo "("; VERB=safe; $TOOL $VERB foo',
        "quoted-open-paren-inflates-depth-stays-denied-as-a-disclosed-residual",
    ),
    # Round 41 (the PR's own designated final review round), the disclosed
    # heredoc-body-tokenized-as-live-command-text over-denial residual
    # (issue #1520): a denied phrase sitting inside pure heredoc DATA
    # triggers a denial even though bash only hands that text to the
    # receiving command's stdin, never re-parses it as shell syntax. See
    # `tokenize()`'s own module-docstring disclosure.
    (
        "cat <<EOF\npip install foo\nEOF",
        "heredoc-body-text-mistaken-for-a-live-pip-install-stays-denied-as-a-disclosed-residual",
    ),
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
    # Found live by Step 8 independent review, sixteenth round (issue
    # #1326): the array-literal counterpart of DENIED_INDIRECTION_
    # COMMANDS's own array-literal cases above, for git push specifically
    # -- `_rule_array_literal_content`'s own recursive check (see its own
    # docstring) sees this via the SAME `_is_git_push_segment` scan a
    # top-level `git push` already gets, since the array's own inner
    # content is classified as if it were its own standalone command.
    ('A=(git push origin main); "${A[@]}"', "array-literal-hides-git-push-still-warn-path"),
    # Found live by Step 8 independent review, eighteenth round (issue
    # #1326): the git-push counterpart of the unassigned-leading-ref
    # cases above -- `A=($NEVERSET git push origin main)` word-splits
    # NEVERSET away to nothing at real bash runtime, landing `git push`
    # as the array's own real first elements.
    (
        'A=($NEVERSET git push origin main); "${A[@]}"',
        "array-literal-unassigned-leading-ref-hides-git-push-still-warn-path",
    ),
    # Found live by Step 8 independent review, nineteenth round (issue
    # #1326): the git-push counterpart of DENIED_INDIRECTION_COMMANDS's
    # own outer-scope-variable case above -- a tool/verb built from a
    # variable assigned OUTSIDE the array literal's own span, for git
    # push specifically.
    (
        'T=git; V=push; ARR=($T $V origin main); "${ARR[@]}"',
        "array-literal-outer-scope-vars-hide-git-push-still-warn-path",
    ),
    # Found live by Step 8 independent review, twenty-second round (issue
    # #1326): `_is_git_push_segment`'s own flag-skip loop used to `break`
    # the instant it met ANY dynamic-shaped token, abandoning the scan
    # rather than looking past a token that vanishes to nothing at real
    # bash runtime -- confirmed live via a real bash proxy (stand-in
    # `git` binary on PATH) that this genuinely runs `git push origin
    # main` once the decoy word-splits away.
    ("git -v $NEVERSET push origin main", "git-push-unassigned-leading-flag-decoy-still-warn-path"),
    # Found live by Step 8 independent review, twenty-third round (issue
    # #1326): the `-c`/long-value-flag branch of the SAME flag-skip loop
    # had two further gaps in miniature -- (1) it never looked past a
    # decoy to find `-c`'s own real value, so the outer loop's own
    # decoy-skip consumed the decoy first and landed on the real value
    # token as an unclaimed, never-consumed token instead, one position
    # short of `push`; (2) it only ever consumed a LITERAL value, never
    # an assigned, non-vanishing DYNAMIC one. Both confirmed live via a
    # real `git` binary (2.43.0) that `-c user.name=x push origin main`
    # genuinely reaches push dispatch (`error: src refspec main does not
    # match any` against an empty scratch repo -- a real ref-lookup
    # failure, not a config-parse error) -- unlike a non-dotted
    # placeholder value, which real git rejects before ever reaching a
    # subcommand at all.
    (
        "git -c $NEVERSET user.name=x push origin main",
        "git-push-c-flag-value-past-leading-decoy-still-warn-path",
    ),
    (
        "CFG=user.name=x; git -c $CFG push origin main",
        "git-push-c-flag-assigned-dynamic-value-still-warn-path",
    ),
    # Found live by Step 8 independent review, twenty-fourth round (issue
    # #1326): a variable assigned the EMPTY STRING (not merely unset)
    # word-splits away IDENTICALLY to a genuinely-unset one at real bash
    # runtime -- `_token_is_all_unassigned_refs` used to only ask "is
    # NAME a key in NAME_TO_VALUE at all," never "does NAME's own
    # assigned value actually survive word-splitting," so this decoy was
    # wrongly treated as NOT vanishing. Confirmed live via real bash
    # that `git -v $CFG push origin main` (CFG assigned "") real-expands
    # to `git -v push origin main`.
    ("CFG=; git -v $CFG push origin main", "git-push-empty-assigned-variable-still-warn-path"),
    # Found live by Step 8 independent review, twenty-fifth round (issue
    # #1326): the twenty-fourth round's own empty-string fix was scoped
    # too narrowly to the BARE form only -- a plain, UN-subscripted
    # braced reference (`${CFG}`) has no array-content ambiguity at all
    # (it is exactly the braced spelling of the same bare scalar
    # reference) and was STILL wrongly left undetected purely because
    # of the `{}` spelling. Confirmed live via real bash that `git -v
    # ${CFG} push origin main` (CFG assigned "") real-expands to `git -v
    # push origin main` identically to the bare form.
    ("CFG=; git -v ${CFG} push origin main", "git-push-plain-braced-empty-assigned-variable-still-warn-path"),
    # Found live by Step 8 independent review, twenty-fifth round (issue
    # #1326): a value consisting ENTIRELY of IFS whitespace (default IFS
    # is space/tab/newline) ALSO word-splits away to nothing at real
    # bash runtime, identically to a literally empty value -- the
    # twenty-fourth round's own fix used raw Python truthiness, which
    # `" "` passes (only `" ".strip()` is falsy). Confirmed live via
    # real bash that `CFG=" "; git -v $CFG push origin main` real-
    # expands to `git -v push origin main`.
    ('CFG=" "; git -v $CFG push origin main', "git-push-all-ifs-whitespace-assigned-variable-still-warn-path"),
    # Found live by Step 8 independent review, twenty-eighth round
    # (issue #1326): once the command itself reassigns `IFS`, a value
    # like `\r` -- which does NOT vanish under bash's own DEFAULT `$IFS`
    # -- must fail closed and be treated as possibly vanishing anyway,
    # since this module cannot know the reassigned `$IFS` doesn't
    # include `\r`. Confirmed live via real bash that `IFS="\r";
    # CFG="\r"; git -v $CFG push origin main` (double-quoted so the
    # carriage return survives shlex's own tokenization -- an unquoted
    # `\r` is absorbed as ordinary whitespace before this code ever
    # runs) genuinely word-splits `$CFG` away under the reassigned IFS.
    (
        'IFS="\r"; CFG="\r"; git -v $CFG push origin main',
        "git-push-carriage-return-decoy-with-ifs-reassigned-still-warn-path",
    ),
    # Found live by Step 8 independent review, twenty-ninth round (issue
    # #1326): the twenty-eighth round's own blanket `$IFS`-reassignment
    # rule reopened a hard-deny bypass strictly broader and easier to
    # trigger than the one it closed -- an ordinary, everyday pattern (a
    # CSV-style IFS reassignment paired with an ordinary `git -c`
    # invocation), no exotic byte tricks needed. `-c`'s own value-
    # consumption loop wrongly treated the REAL, non-vanishing config
    # value as a decoy to skip past, landing on and consuming the
    # literal `push` token itself as `-c`'s own value instead. Confirmed
    # live via real bash that `IFS=,; CFG=user.name=x; git -c $CFG push`
    # real-expands to `git -c user.name=x push`, a genuine push.
    (
        "IFS=,; CFG=user.name=x; git -c $CFG push",
        "git-push-real-config-value-past-unrelated-ifs-reassignment-still-warn-path",
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


# --- Finding 5: git checkout/restore gated on a live git-diff check (issue
# #1375). End-to-end regression suite for hooks/check-bash-safety.sh's own
# new wrapper step, matching this file's own established convention: run
# the shipped script via subprocess against a real scratch git repo, rather
# than re-deriving its behavior in Python.


def _git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )


def _init_repo_with_committed_file(repo_dir: Path, filename: str = "f.py", content: str = "hello\n") -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    _git(repo_dir, "init", "-q")
    # Pinned explicitly rather than relying on the host's own
    # `init.defaultBranch` (matches `_init_diverged_repo`'s own established
    # convention above, for the identical determinism reason): a test that
    # later checks out a branch literally named "main" must not depend on
    # what a given git installation happens to default to.
    _git(repo_dir, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    file_path = repo_dir / filename
    file_path.write_text(content)
    _git(repo_dir, "add", filename)
    _git(repo_dir, "commit", "-q", "-m", "base commit")
    return file_path


def test_checkout_denied_when_target_has_uncommitted_changes(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    result = run("git checkout -- f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "f.py" in payload["systemMessage"]
    assert "git stash" in payload["systemMessage"]


def test_checkout_denied_when_the_command_uses_an_ordinary_line_continuation(tmp_path: Path) -> None:
    """CRITICAL regression pin (round-3 independent review, issue #1375).
    An everyday line-wrapping style for a long git command -- a trailing
    backslash before the newline -- must still resolve to the real path
    (`f.py`), not a path with a literal leading newline baked in that the
    live `git diff` check would silently run against a nonexistent path
    and allow through."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    result = run("git checkout -- \\\nf.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "f.py" in payload["systemMessage"]


def test_checkout_denied_for_pathspec_from_file(tmp_path: Path) -> None:
    """CRITICAL regression pin (round-5 independent review, issue #1375).
    `_git_restore_paths` already hard-denied `--pathspec-from-file`, but
    `_git_checkout_paths` never recognized it -- a single positional after
    it fell through to the honest bare-SOMENAME Non-goal, which is the
    WRONG treatment for a flag whose value is a file naming the real
    pathspecs. Live-verified before the fix: with a tracked file listed
    in that control file dirtied, the wrapper allowed the command
    unconditionally and the real checkout silently discarded the change."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    (repo_dir / "files.txt").write_text("f.py\n")
    result = run("git checkout --pathspec-from-file files.txt", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "pathspec-from-file" in payload["systemMessage"]


def test_checkout_allowed_when_a_comment_after_a_line_continuation_names_an_unrelated_dirty_file(
    tmp_path: Path,
) -> None:
    """CRITICAL regression pin (round-6 independent review, issue #1375).
    `_strip_comments` used to wrongly clear its own boundary status across
    a genuine line continuation, so a `#`-comment sitting on the continued
    line was never recognized as a comment -- its text (here naming an
    unrelated, genuinely dirty file) got swept into `checkout_restore_paths`
    as a phantom candidate and produced a misleading deny. The real
    checkout target (`f.py`) is untouched; `auth.py` is dirty but never
    referenced by the actual command, only by the comment text."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    (repo_dir / "auth.py").write_text("hello\n")
    _git(repo_dir, "add", "auth.py")
    _git(repo_dir, "commit", "-q", "-m", "add auth.py")
    (repo_dir / "auth.py").write_text("hello\ndirty\n")
    result = run(
        "git checkout -- f.py \\\n# TODO revisit auth.py later\n",
        payload_cwd=str(repo_dir),
    )
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    assert result.stdout == ""


def test_checkout_allowed_when_a_trailing_redirect_names_an_unrelated_dirty_file(tmp_path: Path) -> None:
    """CRITICAL false-positive regression pin (round-15 independent
    review, issue #1375). Round 14 taught `_find_git_checkout_restore`
    and `_first_surviving_segment_word` to skip a redirect clause, but
    never taught the path-extraction functions the same lesson -- a
    redirect operator and its target were swept into
    `checkout_restore_paths` as if they were real git path arguments.
    The real checkout target (`f.py`) is untouched; `unrelated.log` is
    dirty but only ever used as an append-redirect target, which can
    never discard its existing content."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    (repo_dir / "unrelated.log").write_text("hello\n")
    _git(repo_dir, "add", "unrelated.log")
    _git(repo_dir, "commit", "-q", "-m", "add unrelated.log")
    (repo_dir / "unrelated.log").write_text("hello\ndirty\n")
    result = run("git checkout -- f.py >> unrelated.log", payload_cwd=str(repo_dir))
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    assert result.stderr == ""


def test_checkout_denied_when_a_digit_shaped_path_sits_before_a_redirect(tmp_path: Path) -> None:
    """CRITICAL data-loss regression pin (round-16 independent review,
    issue #1375). `tokenize()`'s own shlex punctuation-splitting cannot
    distinguish a fused `2>file` (a genuine fd-redirect prefix, no
    argument) from a spaced `2 >file` (the literal word `2` followed by
    a separate redirect) -- both produce the identical token sequence.
    The classifier's own former digit-consuming redirect heuristic
    wrongly guessed "consumed by the redirect" here, silently dropping a
    real, dirty, tracked file named `2` from `checkout_restore_paths`.
    `realfile.py` here is clean; `2` is the only genuinely dirty file."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir, filename="realfile.py")
    file_path = _init_repo_with_committed_file(repo_dir, filename="2")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("git checkout -- realfile.py 2 >target.txt", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_behind_multiple_redirects_including_a_digit_prefixed_one(tmp_path: Path) -> None:
    """CRITICAL false-negative regression pin (round-16 independent
    review, issue #1375, own follow-up). Making the strict, digit-free
    redirect check the ONLY one in use would make the subcommand-finding
    walk stop on a bare digit token sitting in front of a genuine
    `2>&1`-shaped redirect, so a fully literal, unambiguous checkout
    behind multiple redirects would go entirely unrecognized (the live
    wrapper check never even running) -- confirmed as a regression this
    same round's own fix would otherwise introduce."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("git > out.log 2>&1 checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_for_a_real_checkout_hidden_behind_a_commented_paren_in_a_substitution(
    tmp_path: Path,
) -> None:
    """CRITICAL, full-classifier-bypass regression pin (round-7
    independent review, issue #1375). A `$(...)` embedded inside an
    outer double-quoted string re-enters ordinary, comment-aware command
    parsing in real bash -- a `)` inside a `#`-comment inside it does
    NOT end the substitution. The classifier used to not know this,
    leaving the comment (and its embedded `)`) unstripped; that stray
    `)` then made the command-substitution paren counter mistake it for
    the real closing paren, silently dropping everything after it --
    including the real `git checkout` on the next line -- from all
    classification. Live-verified before the fix: the embedded checkout
    ran for real and discarded an uncommitted change while this wrapper
    allowed the command outright."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py", content="ORIGINAL CONTENT\n")
    file_path.write_text("UNCOMMITTED LOCAL EDIT\n")
    command = 'x="$(echo hi #comment with paren ) here\ngit checkout -- dirty.py)"'
    result = run(command, payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "dirty.py" in payload["systemMessage"]
    assert file_path.read_text() == "UNCOMMITTED LOCAL EDIT\n"


def test_checkout_denied_from_a_subdirectory_when_target_has_uncommitted_changes(tmp_path: Path) -> None:
    """The near-miss's own exact shape (issue #1375, issue #1128 repair 4):
    replayed from a SUBDIRECTORY of the repo, not just the repo root --
    `.cwd` (Claude Code's own record of the Bash tool call's actual
    working directory) must be what the live check resolves the pathspec
    against, not this hook runner's own `${CLAUDE_PROJECT_DIR:-$(pwd)}`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    subdir = repo_dir / "sub"
    subdir.mkdir()
    result = run("git checkout -- ../f.py", payload_cwd=str(subdir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_checkout_allowed_when_target_is_clean(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("git checkout -- f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_checkout_denied_for_a_staged_no_op_pins_the_disclosed_over_denial(tmp_path: Path) -> None:
    """Disclosed, accepted residual (round-3 independent review, issue
    #1375), pinned rather than left silently uncovered: `git checkout --
    PATH` restores the working tree from the INDEX, not HEAD, so staging a
    change with no further unstaged edit (worktree == index, index !=
    HEAD) makes the checkout a genuine no-op on disk. This check still
    diffs against HEAD and denies it -- over-denial only, the safe
    direction, never a missed real discard. If this check is ever changed
    to diff against the index for the non-`--staged` case, this test's
    own assertion must flip to `returncode == 0` alongside it."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\nstaged\n")
    _git(repo_dir, "add", "f.py")
    result = run("git checkout -- f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    before = file_path.read_text()
    subprocess.run(
        ["git", "checkout", "--", "f.py"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert file_path.read_text() == before, "real git checkout is a no-op here, confirming the denial was spurious"


def test_checkout_dot_denied_when_a_tracked_file_is_dirty(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    result = run("git checkout .", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


@pytest.mark.parametrize("flag", ["--ours", "--theirs", "-2", "-3"])
def test_checkout_conflict_side_flag_denied_when_the_path_is_dirty(tmp_path: Path, flag: str) -> None:
    """Regression pin (round-40 independent review, issue #1375): before
    this fix, `git checkout --ours/--theirs/-2/-3 f.py` fell through to
    the bare-SOMENAME Non-goal (unresolved, never live-checked), even
    though real git flatly refuses to combine a conflict side flag with
    branch switching -- so the single remaining positional is
    unambiguously a path. Must now be denied against a genuinely dirty
    tracked file, the same as plain `git checkout f.py`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    result = run(f"git checkout {flag} f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_conflict_style_value_flag_stays_a_non_goal(tmp_path: Path) -> None:
    """Negative control for the round-40 fix above: `--conflict=<style>`
    does NOT share the `--ours`/`--theirs`/`-2`/`-3` property -- real git
    still genuinely switches branches with it, so a single remaining
    positional stays the bare-SOMENAME Non-goal and is allowed even
    though it happens to name a real, dirty tracked file."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    result = run("git checkout --conflict=merge f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_checkout_denied_for_a_branch_creation_flag_shaped_path_after_double_dash(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-41 independent review, issue
    #1375, the PR's own final review round): a tracked file literally
    NAMED `-b` (or `-B`/`--orphan`/`--pathspec-from-file`), referenced
    after a literal `--` (`git checkout -- -b`, an ordinary, unambiguous
    path reference -- real git guarantees every token after `--` is a
    pathspec, never a flag), used to fold the WHOLE invocation into the
    bare-SOMENAME Non-goal because the pre-fix branch-creation-flag check
    scanned the entire token list, not just the region before `--`. Before
    this fix, the shipped wrapper allowed this command outright (no live
    dirty-file check performed) and a real `git checkout -- -b` silently
    discarded the dirty content."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="./-b")
    file_path.write_text("hello\ndirty\n")
    result = run("git checkout -- -b", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "-b" in payload["systemMessage"]


def test_ordinary_branch_switch_allowed(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("git checkout -b feature-x", payload_cwd=str(repo_dir))
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_restore_denied_when_target_has_uncommitted_changes(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    result = run("git restore f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_staged_allowed_even_when_worktree_is_dirty(tmp_path: Path) -> None:
    """`git restore --staged PATH` never touches the working tree --
    `checkout_restore_paths` stays empty for it (never live-checked), so
    this must be allowed regardless of the file's own working-tree
    dirtiness."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir)
    file_path.write_text("hello\ndirty\n")
    result = run("git restore --staged f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_checkout_denied_when_payload_cwd_is_missing(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("git checkout -- f.py", payload_cwd=None)
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert ".cwd" in payload["systemMessage"]


def test_checkout_denied_when_payload_cwd_is_not_a_git_repo(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    result = run("git checkout -- f.py", payload_cwd=str(not_a_repo))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "not inside a git working tree" in payload["systemMessage"]


def test_checkout_allowed_on_unborn_head_with_no_conflicting_content(tmp_path: Path) -> None:
    """A fresh repo with no commits yet has no HEAD to diff against --
    must fall back to the empty-tree hash rather than spuriously denying a
    genuinely clean fresh repo (issue #1375's own Acceptance Criteria
    Map)."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q")
    result = run("git checkout -- x.txt", payload_cwd=str(repo_dir))
    assert result.returncode == 0, f"stderr={result.stderr!r}"


def test_checkout_denied_on_unborn_head_when_staged(tmp_path: Path) -> None:
    """The empty-tree-hash fallback still denies when the target genuinely
    differs from an empty tree (staged on a fresh, commit-less repo)."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q")
    (repo_dir / "x.txt").write_text("hello\n")
    _git(repo_dir, "add", "x.txt")
    result = run("git checkout -- x.txt", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_with_tree_relocation_flag_denied_end_to_end(tmp_path: Path) -> None:
    """The classifier's own denial (found before this wrapper step ever
    runs a live git call) reaches the operator through the full shell
    pipeline too: a `-C` global flag makes the wrapper's own fixed `.cwd`
    unsound for this invocation."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run(f"git -C {repo_dir} checkout -- f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_denied_when_an_earlier_pushd_relocates_the_working_tree(tmp_path: Path) -> None:
    """CRITICAL regression pin (round-9 independent review, issue #1375).
    `pushd` relocates the shell's own working directory exactly like `cd`
    does, but only `cd` was recognized here. Live-verified before the
    fix: with a target file dirty relative to a subdirectory but absent
    at the repo root (the PreToolUse payload's own `.cwd`), the wrapper
    allowed `pushd sub &amp;&amp; git checkout -- dirty.py` outright (the
    classifier's own claimed `checkout_restore_paths` checked the wrong
    tree and found nothing) and the real command silently discarded the
    uncommitted change. The deny here is classifier-level (a token-shape
    fact, no live git call), so no such file needs to actually exist for
    this regression pin -- the whole point is that it never gets far
    enough to check."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("pushd sub && git checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_denied_when_an_earlier_dynamic_word_resolves_to_cd(tmp_path: Path) -> None:
    """CRITICAL regression pin (round-10 independent review, issue #1375).
    Round 9's fix only recognized a literal `cd`/`pushd`/`popd` token --
    a dynamic command word that resolves to one of those at real bash
    runtime (`X=cd; $X ...`) was not recognized at all. Live-verified
    before this fix: the classifier's own claimed `checkout_restore_paths`
    would have checked the wrong tree, letting the wrapper's live `git
    diff` check silently allow a real, uncommitted-change discard --
    classifier-level deny (no live git call), so no such file needs to
    actually exist for this regression pin."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("X=cd; $X sub; git checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_allowed_when_an_earlier_dynamic_word_resolves_to_something_harmless(tmp_path: Path) -> None:
    """CRITICAL false-positive regression pin (round-11 independent
    review, issue #1375). Round 10's own first version flagged EVERY
    non-vanishing dynamic `seg[0]`, regardless of what it could actually
    resolve to -- live-verified before this fix to wrongly deny
    `EDITOR=vim; $EDITOR sub; git checkout -- f.py`, a completely safe,
    ordinary command (an `$EDITOR`/`$TOOL` dispatch idiom followed by an
    unrelated, clean checkout), purely because `$EDITOR` is dynamic and
    non-vanishing. The target file here is committed and clean, so a
    correct verdict allows the command outright end-to-end."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("EDITOR=vim; $EDITOR sub; git checkout -- f.py", payload_cwd=str(repo_dir))
    assert result.returncode == 0, f"stderr={result.stderr!r}"


def test_checkout_denied_when_an_earlier_default_clause_could_resolve_to_cd(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-12 independent review, issue
    #1375). `_substitute_var_refs_candidates` does not recursively
    re-expand a `${NAME:-default}` clause's own DEFAULT text -- so when
    the default text is itself a `$OTHER` reference, the classifier's own
    resolution returned the literal, still-unexpanded string `"$OTHER"`,
    never equal to `cd`/`pushd`/`popd` as plain text even when `$OTHER`
    genuinely holds one of those at real bash runtime. Live-verified
    before this fix: `OTHER=cd; ${UNSET:-$OTHER} sub; git checkout --
    dirty.py` was wrongly allowed outright, and the real command silently
    discarded a genuinely dirty `dirty.py`. The deny here is
    classifier-level (a token-shape fact, no live git call), so no such
    file needs to actually exist for this regression pin."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("OTHER=cd; ${UNSET:-$OTHER} sub; git checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_denied_when_a_dynamic_relocator_sits_behind_a_leading_vanishing_decoy(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-13 independent review, issue
    #1375). The classifier's own cwd-relocation check only ever inspected
    a segment's first token -- when that first token itself genuinely
    vanishes at real bash runtime (e.g. a bare reference to a name never
    assigned), the token that actually survives to become the real
    command word was never itself checked. Live-verified before this fix:
    `X=cd; $NEVERSET $X sub; git checkout -- dirty.py` (`NEVERSET`
    genuinely never assigned) was wrongly allowed outright, and the real
    command silently discarded a genuinely dirty `dirty.py` -- real bash
    genuinely runs `cd sub` there. The deny here is classifier-level (a
    token-shape fact, no live git call), so no such file needs to
    actually exist for this regression pin."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("X=cd; $NEVERSET $X sub; git checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_denied_when_a_dynamic_relocator_sits_behind_a_leading_redirect(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-14 independent review, issue
    #1375). A leading I/O-redirection clause -- ordinary, legal bash
    syntax -- made the classifier's own leading-decoy-skip walk return
    the redirect operator token itself as the "surviving word," so the
    real, cd-resolving `$X` one position later was never checked.
    Live-verified before this fix: `X=cd; > /dev/null $X sub; git
    checkout -- dirty.py` was wrongly allowed outright, and the real
    command silently discarded a genuinely dirty `dirty.py`. The deny
    here is classifier-level (a token-shape fact, no live git call), so
    no such file needs to actually exist for this regression pin."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("X=cd; > /dev/null $X sub; git checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_denied_when_a_redirect_sits_between_git_and_the_subcommand(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-14 independent review, issue
    #1375). A fully literal command -- no dynamic content at all -- with
    a redirect between `git` and its subcommand was invisible to
    detection entirely: the redirect operator token was mistaken for the
    subcommand position and the scan gave up, so `checkout_restore_paths`
    resolved empty and the live wrapper check never even ran.
    Live-verified before this fix: `git > /dev/null checkout -- dirty.py`
    was wrongly allowed outright, and the real command silently discarded
    a genuinely dirty `dirty.py`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("git > /dev/null checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_git_itself_is_a_dynamic_word(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-14 independent review, issue
    #1375). Only a LITERAL `git` token was ever recognized as the start
    of a checkout/restore invocation -- live-verified before this fix:
    `G=git; $G checkout -- dirty.py` was wrongly allowed outright, even
    though `$G` unambiguously resolves to `git`, and the real command
    silently discarded a genuinely dirty `dirty.py`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("G=git; $G checkout -- dirty.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_a_dynamic_git_token_sits_inside_a_command_substitution(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-18 independent review, issue
    #1375). A `git` token held in a variable assigned OUTSIDE a `$(...)`
    command substitution -- an ordinary "hold the tool name in a
    variable" idiom, not an exotic precondition -- defeated checkout/
    restore recognition entirely, not merely under-extracted it: the
    recursive classification of a substitution's own inner content
    passed no outer scope, so `$G` could never resolve to `git` there
    even though it unambiguously does at real bash runtime. Live-verified
    before this fix: `G=git; x=$($G checkout -- dirty.py)` was wrongly
    allowed outright through the real wrapper, and the real command
    afterward silently discarded a genuinely dirty `dirty.py`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("G=git; x=$($G checkout -- dirty.py)", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_a_dynamic_git_token_sits_inside_a_quoted_command_substitution(
    tmp_path: Path,
) -> None:
    """Companion to the unquoted-form pin above, for the quoted/fused
    `$(...)` shape (`_find_fused_command_substitution`, recursed into via
    `classify()` on the inner TEXT rather than `_classify_tokens` on
    inner TOKENS) -- the two shapes are handled by separate code paths in
    `_rule_command_substitution_content`, both needed the outer-scope fix
    (round-18 independent review, issue #1375)."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run('G=git; x="$($G checkout -- dirty.py)"', payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_a_dynamic_git_token_is_reassigned_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-19 independent review, issue
    #1375). `_assigned_raw_values`'s own order-blind, last-occurrence-
    wins collapse meant an entirely ordinary shell idiom -- reusing a
    variable name for a later, unrelated purpose after it was already
    used as `git` -- silently defeated recognition entirely, since the
    variable's own dict entry resolved to the LATER value, not the one
    genuinely in effect at the actual point of use. Live-verified before
    this fix: `TOOL=git; $TOOL checkout -- dirty.py; TOOL=npm` was
    wrongly allowed outright through the real wrapper, and the real
    command afterward silently discarded a genuinely dirty `dirty.py`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("TOOL=git; $TOOL checkout -- dirty.py; TOOL=npm", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_denied_when_a_dynamic_git_token_is_reassigned_after_use(tmp_path: Path) -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-19 finding was confirmed live for both subcommands."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("TOOL=git; $TOOL restore dirty.py; TOOL=npm", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_a_dynamic_git_token_inside_a_command_substitution_is_reassigned_after_use(
    tmp_path: Path,
) -> None:
    """Companion to the two pins above, for the command-substitution
    shape: the SAME reassignment-after-use gap, reached through
    `_rule_command_substitution_content`'s own outer-scope threading
    (round 18). Live-verified before this fix: `G=git; x=$($G checkout
    -- dirty.py); G=notgit` was wrongly allowed outright through the real
    wrapper."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("G=git; x=$($G checkout -- dirty.py); G=notgit", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_a_dynamic_cd_relocator_is_reassigned_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-20 independent review, issue
    #1375). `_rule_git_checkout_restore`'s own dynamic-cd-relocation
    check was fed only the ordinary, order-blind `raw_assigned` -- the
    IDENTICAL reassignment-after-use gap round 19 closed for the sibling
    git-token-recognition consumer in the same function, just left open
    here. Live-verified before this fix: `X=cd; $X sub; git checkout --
    dirty.py; X=somethingelse` (reusing a variable name for a later,
    unrelated purpose, the same ordinary idiom round 19's own finding
    used) resolved to a CONFIDENT, WRONG `checkout_restore_paths` claim
    -- `$X` genuinely was `cd` at its actual point of use one statement
    earlier -- and was wrongly allowed outright through the real wrapper.
    The deny here is classifier-level (a token-shape fact, no live git
    call), so no such file needs to actually exist for this regression
    pin."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("X=cd; $X sub; git checkout -- dirty.py; X=somethingelse", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_restore_denied_when_a_dynamic_pushd_relocator_is_reassigned_after_use(tmp_path: Path) -> None:
    """Companion to the `cd` pin above, for `pushd` and `git restore` --
    the round-20 finding was confirmed live for all three
    `_CWD_RELOCATING_COMMANDS` members and both subcommands."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("X=pushd; $X sub; git restore dirty.py; X=somethingelse", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_denied_when_a_dynamic_cd_relocator_is_reassigned_across_a_command_substitution(
    tmp_path: Path,
) -> None:
    """CRITICAL bypass regression pin (round-21 independent review, issue
    #1375). Round 20's own cd-biased fix was scoped to the current
    `_classify_tokens` invocation's own top-level segments only, which
    missed a reassignment straddling a command substitution's OWN
    boundary -- the relocator `$X` is used entirely WITHIN the
    substitution, but the ambiguity lives in the OUTER token stream.
    Live-verified before this fix: `X=cd; y=$($X sub; git checkout --
    dirty.py); X=somethingelse` was wrongly allowed outright through the
    real wrapper. The deny here is classifier-level (a token-shape fact,
    no live git call), so no such file needs to actually exist for this
    regression pin."""
    repo_dir = tmp_path / "repo"
    _init_repo_with_committed_file(repo_dir)
    result = run("X=cd; y=$($X sub; git checkout -- dirty.py); X=somethingelse", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "working tree is at risk" in payload["systemMessage"]


def test_checkout_denied_when_a_path_argument_is_reassigned_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-21 independent review, issue
    #1375). `_resolve_path_tokens`'s own dynamic-path-argument resolution
    is a THIRD consumer of the order-blind `_assigned_raw_values`
    collapse, with no bias mechanism at all before this fix -- the most
    severely reachable of the three reassignment-ambiguity bugs found in
    this feature (rounds 19-21): no command substitution, no cd/pushd/
    popd, not even multiple statements beyond the reassignment itself are
    required. Live-verified before this fix: `F=dirty.py; git checkout --
    $F; F=other.py` resolved `checkout_restore_paths` to `('other.py',)`
    alone -- a CONFIDENT, WRONG claim, since `$F` genuinely was
    `dirty.py` at its actual point of use -- so the real wrapper's own
    live `git diff --quiet` check ran against the harmless `other.py`
    and never checked the genuinely dirty `dirty.py` at all, wrongly
    allowing the command outright."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("F=dirty.py; git checkout -- $F; F=other.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_denied_when_a_path_argument_is_reassigned_after_use(tmp_path: Path) -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-21 finding was confirmed live for both subcommands."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("F=dirty.py; git restore $F; F=other.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_a_fused_path_reference_is_reassigned_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-23 independent review, issue
    #1375). Round 21's own history-widening fix was scoped to a token
    that is EXACTLY one bare/braced whole-token reference -- the ordinary
    `"$DIR/$FILE"` path-join idiom (a reference FUSED with a literal `/`
    and another reference in the SAME token) fell through to the
    ordinary, un-widened, order-blind resolution, producing a CONFIDENT,
    WRONG `checkout_restore_paths` claim: `DIR=sub; FILE=dirty.py; git
    checkout -- "$DIR/$FILE"; DIR=other` resolved to `('other/dirty.py',)`
    alone, even though `$DIR` genuinely was `sub` at its actual point of
    use one statement earlier -- so the live `git diff --quiet` check ran
    against the wrong, nonexistent `other/dirty.py` and the genuinely
    dirty `sub/dirty.py` was never checked at all."""
    repo_dir = tmp_path / "repo"
    (repo_dir / "sub").mkdir(parents=True)
    file_path = _init_repo_with_committed_file(repo_dir, filename="sub/dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run(
        'DIR=sub; FILE=dirty.py; git checkout -- "$DIR/$FILE"; DIR=other',
        payload_cwd=str(repo_dir),
    )
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_denied_when_a_fused_path_reference_is_reassigned_after_use(tmp_path: Path) -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-23 finding was confirmed live for both subcommands."""
    repo_dir = tmp_path / "repo"
    (repo_dir / "sub").mkdir(parents=True)
    file_path = _init_repo_with_committed_file(repo_dir, filename="sub/dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run(
        'DIR=sub; FILE=dirty.py; git restore "$DIR/$FILE"; DIR=other',
        payload_cwd=str(repo_dir),
    )
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_the_path_name_is_reassigned_to_a_dynamic_value_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-24 independent review, issue
    #1375). `_assigned_raw_values`/`_assigned_raw_value_history` both skip
    a dynamic-RHS assignment token entirely, so a name's own EARLIER,
    static assignment stayed on file untouched by a LATER, dynamic
    reassignment of the SAME name -- silently trusted as still current.
    Live-verified before this fix: `DIR=sub; DIR=$(echo other); git
    checkout -- $DIR` resolved `checkout_restore_paths` to `('sub',)` --
    confidently the WRONG, STALE value, since real bash genuinely
    resolves `$DIR` to whatever the substitution evaluates to at its
    actual point of use, not `sub`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("DIR=dirty.py; DIR=$(echo other.py); git checkout -- $DIR", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_denied_when_the_path_name_is_reassigned_to_a_dynamic_value_after_use(tmp_path: Path) -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-24 finding was confirmed live for both subcommands."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("DIR=dirty.py; DIR=$(echo other.py); git restore $DIR", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_an_indirect_reference_target_is_reassigned_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-24 independent review, issue
    #1375), second class: round 23's own `_multi_valued_names_referenced`
    widened only the FIRST-level name of a `${!NAME}` indirect reference,
    never the SECOND-level target it actually points to at the point of
    use. Live-verified before this fix: `TARGET=dirty.py; C=TARGET; git
    checkout -- ${!C}; TARGET=other.py` resolved `checkout_restore_paths`
    to `('other.py',)` alone -- the WRONG, order-blind-collapsed last
    value of TARGET, since real bash genuinely resolves `${!C}` to
    `dirty.py` at its actual point of use."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("TARGET=dirty.py; C=TARGET; git checkout -- ${!C}; TARGET=other.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_denied_when_an_indirect_reference_target_is_reassigned_after_use(tmp_path: Path) -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-24 finding's second class was confirmed live for both
    subcommands."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("TARGET=dirty.py; C=TARGET; git restore ${!C}; TARGET=other.py", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_the_path_name_is_dynamically_appended_to_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-25 independent review, issue
    #1375). `_ASSIGN_RE` never matches bash's own `NAME+=value` compound/
    append-assignment operator at all, so round 24's own `_names_with_
    dynamic_assignment` -- keyed entirely off `_ASSIGN_RE` -- was
    completely blind to an appended name. Live-verified before this fix:
    `DIR=dirty.py; for i in 1; do DIR+=$(echo .bak); done; git checkout
    -- $DIR` resolved `checkout_restore_paths` to `('dirty.py',)` -- the
    STALE, pre-append value, since real bash genuinely resolves `$DIR` to
    `dirty.py.bak` at its actual point of use."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py.bak")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run(
        "DIR=dirty.py; for i in 1; do DIR+=$(echo .bak); done; git checkout -- $DIR",
        payload_cwd=str(repo_dir),
    )
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_denied_when_the_path_name_is_dynamically_appended_to_after_use(tmp_path: Path) -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-25 finding was confirmed live for both subcommands."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="dirty.py.bak")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run(
        "DIR=dirty.py; for i in 1; do DIR+=$(echo .bak); done; git restore $DIR",
        payload_cwd=str(repo_dir),
    )
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_the_path_name_is_reassigned_via_read_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-26 independent review, issue
    #1375). Neither `_ASSIGN_RE` nor `_APPEND_ASSIGN_RE` recognizes bash's
    own `read NAME` builtin as a reassignment at all, so round 25's own
    `_names_with_dynamic_assignment` was completely blind to a name
    reassigned this way. Live-verified before this fix: `DIR=sub; read
    DIR <<< "other"; git checkout -- $DIR` resolved `checkout_restore_
    paths` to `('sub',)` -- the STALE, pre-reassignment value, since real
    bash genuinely resolves `$DIR` to `other` at its actual point of use
    (confirmed via `bash -c 'DIR=sub; read DIR <<< "other"; echo
    "DIR=[$DIR]"'` -> `DIR=[other]`)."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="other")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run(
        'DIR=sub; read DIR <<< "other"; git checkout -- $DIR',
        payload_cwd=str(repo_dir),
    )
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_restore_denied_when_the_path_name_is_reassigned_via_read_after_use(tmp_path: Path) -> None:
    """Companion to the checkout pin above, for `git restore`."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="other")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run(
        'DIR=sub; read DIR <<< "other"; git restore $DIR',
        payload_cwd=str(repo_dir),
    )
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_when_the_path_name_is_reassigned_via_an_array_element_after_use(tmp_path: Path) -> None:
    """CRITICAL bypass regression pin (round-26 independent review, issue
    #1375). Bash's own array-element assignment (`NAME[i]=value`) is
    invisible to `_ASSIGN_RE`/`_APPEND_ASSIGN_RE` -- both anchor
    immediately after NAME's own identifier characters, with no `[...]`
    in between. Live-verified before this fix: `arr=x; arr[0]=other; git
    checkout -- $arr` resolved `checkout_restore_paths` to `('x',)` --
    the STALE, pre-reassignment value (confirmed via `bash -c 'arr=x;
    arr[0]=other; echo "arr=[$arr]"'` -> `arr=[other]`)."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="other")
    file_path.write_text("UNCOMMITTED WORK -- must not be discarded\n")
    result = run("arr=x; arr[0]=other; git checkout -- $arr", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"


def test_checkout_denied_in_a_real_merge_conflict_names_the_conflict_remedy(tmp_path: Path) -> None:
    """A real merge conflict (issue #1375's own Acceptance Criteria Map):
    the deny message names a remedy that actually works mid-conflict
    (`git checkout -m -- PATH`), not only `git stash` (which fails with
    "needs merge" while a conflict is unresolved)."""
    repo_dir = tmp_path / "repo"
    file_path = _init_repo_with_committed_file(repo_dir, filename="f.txt", content="line1\n")
    _git(repo_dir, "checkout", "-q", "-b", "branch-a")
    file_path.write_text("line1-a\n")
    _git(repo_dir, "commit", "-q", "-am", "change on a")
    _git(repo_dir, "checkout", "-q", "-b", "branch-main", "main")
    file_path.write_text("line1-main\n")
    _git(repo_dir, "commit", "-q", "-am", "change on main")
    subprocess.run(
        ["git", "merge", "branch-a", "-q"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )
    result = run("git checkout -- f.txt", payload_cwd=str(repo_dir))
    assert result.returncode == 2, f"stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert "git checkout -m" in payload["systemMessage"]

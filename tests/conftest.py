"""Shared pytest fixtures/helpers for this repository's tests/ suite."""

from __future__ import annotations

import io
import pathlib
import re
import subprocess
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Unsatisfiable(BaseModel):
    """Throwaway model with one required field, used only by
    `make_validation_error` below to manufacture a real pydantic
    `ValidationError` instance."""

    required: int


def make_validation_error() -> ValidationError:
    """A genuine `pydantic.ValidationError` instance, for monkeypatching a
    gate's own `*Args` model class to exercise its `except ValidationError`
    branch in tests. Several `.github/scripts/gitapex_gate_*.py` gates
    (issue #1062, wave 3 of #1040's batch) wrap `argparse`-guaranteed CLI
    input in a pydantic model whose fields can never actually fail
    validation from real CLI input -- their `except ValidationError` branch
    is therefore only reachable by monkeypatching the model class itself to
    raise, not by constructing genuinely invalid input."""
    try:
        _Unsatisfiable()  # type: ignore[call-arg]
    except ValidationError as error:
        return error
    raise AssertionError("expected ValidationError")


class FakeStdin:
    """Just the surface a CLI's `main()` uses: `sys.stdin.buffer.read()`.

    Shared by every test that monkeypatches `sys.stdin` to feed a script
    non-UTF-8 (or otherwise arbitrary) bytes through its
    `sys.stdin.buffer.read().decode("utf-8")` read path, so a future change
    to this mock's surface only needs to land once (same rationale as
    `assert_path_is_gitignored` below).
    """

    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


# git check-ignore -v prefixes a match with "source:linenum:pattern", then a
# tab and the matched pathname. The pattern (and, in principle, a Windows
# drive-letter source path) can itself contain colons, so a plain split on
# the first ":" can misidentify the source -- anchoring on ":<digits>:" (the
# linenum field, which is always a bare integer) instead finds the correct
# boundary regardless of what precedes or follows it.
_CHECK_IGNORE_SOURCE_RE = re.compile(r"^(.*):\d+:")


def assert_path_is_gitignored(path: pathlib.Path, description: str) -> None:
    """Assert ``path`` is ignored by this repository's own tracked
    `.gitignore` (not an ambient exclude source elsewhere on the machine).

    Shared by every `test_gitignore_*.py` drift gate so a future fix to
    the ambient-exclude-source check only needs to land once.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-v", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{description} is no longer covered by .gitignore."
    match = _CHECK_IGNORE_SOURCE_RE.match(result.stdout)
    assert match is not None, f"could not parse 'git check-ignore -v' output for {description}: {result.stdout!r}"
    source = match.group(1)
    repo_gitignore = REPO_ROOT / ".gitignore"
    assert pathlib.Path(source).resolve() == repo_gitignore.resolve(), (
        f"{description} is ignored, but by {source!r} instead of this "
        f"repository's own {repo_gitignore} -- an ambient exclude source "
        "(global core.excludesFile, $GIT_DIR/info/exclude) is masking a "
        "possibly-removed repository rule."
    )


def _parse_workflow(workflow_name: str) -> Any:
    """`.github/workflows/<workflow_name>` parsed as YAML."""
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8"))


def _workflow_steps(workflow_name: str) -> list[Any]:
    """Every `jobs.*.steps[]` entry of `.github/workflows/<workflow_name>`."""
    return [step for job in _parse_workflow(workflow_name)["jobs"].values() for step in job.get("steps", [])]


def assert_workflow_has_no_trigger_path_filter(workflow_name: str) -> None:
    """Assert `.github/workflows/<workflow_name>`'s trigger carries neither a
    `paths:` nor a `paths-ignore:` filter, in any YAML style.

    Shared by every gate workflow's own no-paths-filter drift test (same
    rationale as `assert_path_is_gitignored` above). `paths-ignore:` is
    rejected too, not only `paths:`: GitHub's own trigger filter accepts
    either key to the same stuck-Pending effect.

    The trigger keys are read off the parsed YAML rather than matched as
    text: a line-prefix scan only ever sees a filter written in block style
    on a line of its own, so a flow-style trigger --
    `pull_request: {paths: ["hooks/**"]}`, the style
    `plugin-root-brace-notation-gate.yml` already writes its own trigger in
    -- or a quoted `"paths":` key would defeat it while a real,
    parser-visible filter still applied. Parsing costs one lookup to work
    around PyYAML's default YAML-1.1 resolver reading the bare `on` key as
    boolean `True` rather than the string `"on"`. Each caller's own pointer
    comment for this very invariant contains the literal substring
    `` `paths:` `` in prose, which a whole-file text check would misread as
    the trigger itself carrying a filter -- parsing sidesteps this too,
    since the parser never offers comments at all. Each caller's own
    docstring states why its workflow must stay unfiltered.
    """
    parsed = _parse_workflow(workflow_name)
    trigger = parsed[True] if True in parsed else parsed["on"]
    # `on: push` and `on: [push, pull_request]` leave nowhere to hang a
    # filter; only the mapping form does, at either of its two levels.
    blocks = (
        [trigger, *(event for event in trigger.values() if isinstance(event, dict))]
        if isinstance(trigger, dict)
        else []
    )
    filters = sorted(str(key) for block in blocks for key in block if str(key).startswith("paths"))
    assert not filters, f"{workflow_name}'s trigger carries {filters}: {trigger}"


_MERGE_BASE_CALL = 'merge_base=$(git merge-base "$BASE_SHA" "$HEAD_SHA")'


def _strip_shell_comments(script: str) -> str:
    """`script` with its `#` comments removed.

    A `#` opens a comment only at the start of a word (POSIX's own rule,
    not a simplification of it): the first character of the line, or any
    character preceded by whitespace or a control operator (`;`, `&`,
    `|`, `(`, `)`, `<`, `>`). One of the real producer lines this runs
    over is `git ls-tree ... | sed -E 's#^skills/##' | sort`, whose three
    `#` characters are all data (each is preceded by a non-blank, non-
    operator character) -- and a decoy comment attached directly after an
    operator with no space, e.g. `cmd;# fake`, is still a real comment a
    shell would honor, so treating only whitespace as a word boundary
    understated the rule and let such a decoy hide as ordinary script
    text. A backslash also escapes the character right after it (a
    literal, not a quote-toggle or comment-opener), including inside a
    double-quoted string -- a `#` following an escaped `\\"` is still
    inside that string, not a fresh word.
    """
    stripped = []
    for line in script.split("\n"):
        quote = ""
        escape = False
        word_start = True
        cut = len(line)
        for index, char in enumerate(line):
            if escape:
                escape = False
                word_start = False
                continue
            if quote:
                if char == "\\" and quote == '"':
                    escape = True
                elif char == quote:
                    quote = ""
                word_start = False
                continue
            if char == "\\":
                escape = True
                word_start = False
            elif char in "\"'":
                quote = char
                word_start = False
            elif char == "#" and word_start:
                cut = index
                break
            elif char in " \t;&|()<>":
                word_start = True
            else:
                word_start = False
        stripped.append(line[:cut])
    return "\n".join(stripped)


# Any spelling of a direct base.sha reference: the quoted/braced/bare forms
# of the $BASE_SHA shell variable, and the raw Actions expression it is
# itself assigned from (see each caller's own `env:` block) -- a producer
# line naming either bypasses "merge-base, not base.sha" independently of
# the $BASE_SHA indirection.
_BASE_SHA_RE = re.compile(r"\$\{?\bBASE_SHA\b\}?|github\.event\.pull_request\.base\.sha")


def assert_workflow_feeds_merge_base_to(workflow_name: str, *producer_commands: str) -> None:
    """Assert `.github/workflows/<workflow_name>` computes `$merge_base` from
    the exact `"$BASE_SHA" "$HEAD_SHA"` pair, in that same step feeds it to a
    line running one of `producer_commands` (`"diff"`, `"ls-tree"`), and
    never diffs `base.sha` directly in any spelling.

    Shared by every gate workflow's own merge-base drift test (same
    rationale as `assert_path_is_gitignored` above). Both assertions are
    scoped to the parsed `jobs.*.steps[].run` content with shell comments
    stripped first, not the whole file as text: a YAML comment, a
    non-comment YAML value outside any `run:` block (a step `name:`, for
    one), or a shell `#` comment restating the removed logic can otherwise
    satisfy either check while the real invariant is gone from the
    executable content. The producer line must carry the word `git`
    followed later by one of `producer_commands` as a word, not the bare
    substring, matched with `.*` rather than contiguously since the real
    invocations read `git -c core.quotePath=false diff ...`, a flag in
    between. `$merge_base` is a plain shell variable, so both halves must
    be satisfied by the same step -- a producer in some later step could
    never have read it.

    `on:` is deliberately never parsed here -- PyYAML's default YAML-1.1
    resolver reads the bare `on` key as boolean `True`, not the string
    `"on"`. Each caller's own docstring states why its workflow must not
    diff against `base.sha` directly.
    """
    producer_re = re.compile(
        r"\bgit\b.*(" + "|".join(rf"\b{re.escape(command)}\b" for command in producer_commands) + ")"
    )
    scripts = [_strip_shell_comments(step["run"]) for step in _workflow_steps(workflow_name) if "run" in step]
    fed_merge_base = False
    for script in scripts:
        producers = [line for line in script.split("\n") if producer_re.search(line)]
        offenders = [line for line in producers if _BASE_SHA_RE.search(line)]
        assert not offenders, f"{workflow_name} diffs base.sha directly: {offenders}"
        fed_merge_base = fed_merge_base or (
            _MERGE_BASE_CALL in script and any('"$merge_base"' in line for line in producers)
        )
    assert fed_merge_base, f"{workflow_name} never feeds $merge_base to a {producer_commands} producer: {scripts}"


# The one `ref:` value that makes a checked-out tree *be* the diff's
# post-image, which is what the two line-number-correlating gates need.
_HEAD_SHA_REF = "${{ github.event.pull_request.head.sha }}"


def assert_workflow_checkout_pins_head_sha_with_full_history(workflow_name: str) -> None:
    """Assert every checkout-shaped step in
    `.github/workflows/<workflow_name>` is the pinned `harden-checkout`
    action, passing `ref: <head sha>` and `fetch-depth: 0`.

    Shared by the two gate workflows that correlate diff-derived line numbers
    against tree content (same rationale as `assert_path_is_gitignored`
    above), so this check cannot silently diverge between them. Each caller's
    own docstring states why its gate needs the pin.

    Scoped to the parsed `jobs.*.steps[].with` mapping rather than checked
    against the whole file as text: both workflows' own pointer comment for
    this very invariant contains the literal substring `fetch-depth: '0'` in
    prose, so a whole-file text check passes off the comment alone with the
    real input deleted -- verified live, and the exact defect class this
    repository had already had to close once.

    Every step whose `uses:` mentions `checkout` is inspected, not only ones
    already named `harden-checkout`: an *added*, unpinned `actions/checkout`
    step breaks the post-image correlation exactly as a second, unpinned
    harden-checkout step would, and neither must go unnoticed. The non-empty
    guard is what keeps the loop from passing vacuously if the checkout step
    is renamed or dropped outright.

    `fetch-depth` is compared as text (`'0'` and `0` both parse to the same
    single input value) because the composite action declares it as an
    action input and interpolates it into `actions/checkout`'s own
    `fetch-depth` -- see `.github/actions/harden-checkout/action.yml`. The
    YAML quoting therefore carries no meaning of its own to assert.
    """
    checkout_steps = [
        step for step in _workflow_steps(workflow_name) if "checkout" in str(step.get("uses", "")).lower()
    ]
    assert checkout_steps, f"{workflow_name} has no checkout step"
    for step in checkout_steps:
        uses = str(step.get("uses", ""))
        assert "harden-checkout" in uses, f"{workflow_name} has a non-harden-checkout checkout step: {uses}"
        inputs = step.get("with") or {}
        assert inputs.get("ref") == _HEAD_SHA_REF, f"{workflow_name}: {inputs}"
        assert str(inputs.get("fetch-depth")) == "0", f"{workflow_name}: {inputs}"


def assert_workflow_diff_carries_flags(workflow_name: str, *flags: str) -> None:
    """Assert `.github/workflows/<workflow_name>`'s `git diff -U0` invocation
    carries every one of `flags`.

    Shared by the two gate workflows whose own line-number-correlating
    scripts depend on these flags (same rationale as
    `assert_path_is_gitignored` above). Each caller's own docstring states
    why its gate needs each flag. Reads the raw text rather than parsing
    `run:` content the way the merge-base assertions above do -- this is a
    plain deduplication of two already-identical per-file checks, not a
    hardening pass; behavior is unchanged from before the move.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
    invocation = next(line for line in workflow.split("\n") if "git" in line and "diff -U0" in line)
    for flag in flags:
        assert flag in invocation, invocation
